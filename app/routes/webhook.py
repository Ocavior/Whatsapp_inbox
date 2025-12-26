from fastapi import APIRouter, Request, HTTPException, Depends 
from app.websockets.connection_manager import manager
from fastapi.responses import PlainTextResponse
from datetime import datetime
from app.services.inbox import InboxService
from app.services.whatsapp import WhatsAppService
from app.utils.logger import logger
from app.config import WEBHOOK_VERIFY_TOKEN

router = APIRouter()

@router.get("/webhook")
async def verify_webhook(request: Request):
    """Verify webhook for WhatsApp Business API - NO DEPENDENCIES"""
    
    
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    
    logger.info(f"🔍 Webhook verification attempt:")
    logger.info(f"  - Mode: {mode}")
    logger.info(f"  - Token received: {token}")
    logger.info(f"  - Challenge: {challenge}")
    logger.info(f"  - Expected token: {WEBHOOK_VERIFY_TOKEN}")
     

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully!")
        return PlainTextResponse(content=challenge, status_code=200)
    
    
    logger.warning(f"❌ Webhook verification failed!")
    logger.warning(f"  - Mode match: {mode == 'subscribe'}")
    logger.warning(f"  - Token match: {token == WEBHOOK_VERIFY_TOKEN}")
    
    return PlainTextResponse(content="Verification failed", status_code=403)




@router.post("/webhook")
async def receive_webhook(
    request: Request,
    inbox_service: InboxService = Depends(),
    whatsapp_service: WhatsAppService = Depends()
):
    """Receive incoming messages and status updates from WhatsApp"""
    try:
        
        body_bytes = await request.body()
        signature = request.headers.get("x-hub-signature-256", "")
        
        
        if signature:
            if not whatsapp_service.validate_webhook_signature(body_bytes, signature):
                logger.warning("⚠️ Invalid webhook signature")
                # Uncomment in production:
                raise HTTPException(status_code=401, detail="Invalid signature")
        

        body = await request.json()
        logger.info(f"📨 Received webhook: {body}")
        
        
        entry = body.get("entry", [])
        for webhook_entry in entry:
            changes = webhook_entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                
                
                messages = value.get("messages", [])
                for message in messages:
                    await _process_incoming_message(message, inbox_service, whatsapp_service)
                
                
                statuses = value.get("statuses", [])
                for status in statuses:
                    await _process_status_update(status, inbox_service)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _process_incoming_message(message: dict, inbox_service: InboxService, 
                                   whatsapp_service: WhatsAppService):
    """Process incoming WhatsApp message - WITH WEBSOCKET NOTIFICATION"""
    try:
        message_type = message.get("type")
        from_number = message["from"]
        timestamp = datetime.fromtimestamp(int(message["timestamp"]))
        
        message_data = {
            "user_id": from_number,
            "direction": "inbound",
            "message_type": message_type,
            "body": "",
            "timestamp": timestamp,
            "status": "received",
            "message_id": message["id"]
        }
        
        
        if message_type == "text":
            message_data["body"] = message.get("text", {}).get("body", "")
        elif message_type == "image":
            message_data["body"] = "[Image]"
            message_data["media_id"] = message.get("image", {}).get("id")
            message_data["media_type"] = "image"
            if message.get("image", {}).get("caption"):
                message_data["body"] = message["image"]["caption"]
        elif message_type == "video":
            message_data["body"] = "[Video]"
            message_data["media_id"] = message.get("video", {}).get("id")
            message_data["media_type"] = "video"
            if message.get("video", {}).get("caption"):
                message_data["body"] = message["video"]["caption"]
        elif message_type == "audio":
            message_data["body"] = "[Audio]"
            message_data["media_id"] = message.get("audio", {}).get("id")
            message_data["media_type"] = "audio"
        elif message_type == "document":
            message_data["body"] = "[Document]"
            message_data["media_id"] = message.get("document", {}).get("id")
            message_data["media_type"] = "document"
            filename = message.get("document", {}).get("filename", "")
            if filename:
                message_data["body"] = f"[Document: {filename}]"
        elif message_type == "location":
            location = message.get("location", {})
            lat = location.get("latitude", "")
            lon = location.get("longitude", "")
            message_data["body"] = f"[Location: {lat}, {lon}]"
        elif message_type == "contacts":
            message_data["body"] = "[Contact Card]"
        else:
            message_data["body"] = f"[{message_type.capitalize()}]"
        
        
        await inbox_service.save_message(message_data)
        logger.info(f"✅ Processed incoming message from {from_number}: {message_type}")
        
        
        try:
            await manager.broadcast({
                "type": "new_message",
                "data": {
                    "phone": from_number,
                    "message": message_data["body"],
                    "message_type": message_type,
                    "timestamp": timestamp.isoformat(),
                    "message_id": message["id"],
                    "direction": "inbound"
                }
            })
            logger.info(f"📢 WebSocket notification sent for message from {from_number}")
        except Exception as notif_error:
            logger.error(f"⚠️ Failed to send WebSocket notification: {notif_error}")
            
        
        
        try:
            await whatsapp_service.mark_message_as_read(message["id"])
        except Exception as e:
            logger.warning(f"Could not mark message as read: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error processing incoming message: {e}", exc_info=True)


async def _process_status_update(status: dict, inbox_service: InboxService):
    """Process message status updates (sent, delivered, read, failed) - WITH WEBSOCKET NOTIFICATION"""
    try:
        message_id = status.get("id")
        new_status = status.get("status")
        recipient = status.get("recipient_id")
        
        
        error_info = None
        if new_status == "failed":
            errors = status.get("errors", [])
            if errors:
                error_info = errors[0].get("message", "Unknown error")
        
        if message_id and new_status:
            success = await inbox_service.update_message_status(
                message_id, 
                new_status,
                error_reason=error_info
            )
            
            if success:
                logger.info(f"✅ Updated message {message_id} status to {new_status}")
                
                # 🔔 SEND STATUS UPDATE NOTIFICATION
                try:
                    await manager.broadcast({
                        "type": "message_status",
                        "data": {
                            "message_id": message_id,
                            "status": new_status,
                            "recipient": recipient,
                            "error": error_info,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })
                    logger.info(f"📢 WebSocket status notification sent for {message_id}")
                except Exception as notif_error:
                    logger.error(f"⚠️ Failed to send status notification: {notif_error}")
            else:
                logger.warning(f"⚠️ Could not update message {message_id} status")
            
    except Exception as e:
        logger.error(f"❌ Error processing status update: {e}", exc_info=True)