from fastapi import APIRouter, Request, HTTPException, Depends
from datetime import datetime
from app.services.inbox import InboxService
from app.services.whatsapp import WhatsAppService
from app.utils.logger import logger
from app.config import *

router = APIRouter()

@router.get("/webhook")
async def verify_webhook(
    request: Request,
    whatsapp_service: WhatsAppService = Depends()
):
    """Verify webhook for WhatsApp Business API"""
    params = dict(request.query_params)
    
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    logger.info(f"Webhook verification attempt - Mode: {mode}")
    
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return int(challenge)
    
    logger.warning("Webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification failed")

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
        
        if not whatsapp_service.validate_webhook_signature(body_bytes, signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        body = await request.json()
        logger.info(f"Received webhook: {body}")
        
        
        entry = body.get("entry", [])
        for webhook_entry in entry:
            changes = webhook_entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                
                
                messages = value.get("messages", [])
                for message in messages:
                    await _process_incoming_message(message, inbox_service)
                
                
                statuses = value.get("statuses", [])
                for status in statuses:
                    await _process_status_update(status, inbox_service)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

async def _process_incoming_message(message: dict, inbox_service: InboxService):
    """Process incoming WhatsApp message"""
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
        elif message_type == "video":
            message_data["body"] = "[Video]"
            message_data["media_id"] = message.get("video", {}).get("id")
            message_data["media_type"] = "video"
        elif message_type == "audio":
            message_data["body"] = "[Audio]"
            message_data["media_id"] = message.get("audio", {}).get("id")
            message_data["media_type"] = "audio"
        elif message_type == "document":
            message_data["body"] = "[Document]"
            message_data["media_id"] = message.get("document", {}).get("id")
            message_data["media_type"] = "document"
        else:
            message_data["body"] = f"[{message_type.capitalize()}]"
        
        await inbox_service.save_message(message_data)
        logger.info(f"Processed incoming message from {from_number}")
        
    except Exception as e:
        logger.error(f"Error processing incoming message: {e}")

async def _process_status_update(status: dict, inbox_service: InboxService):
    """Process message status updates"""
    try:
        message_id = status.get("id")
        new_status = status.get("status")
        
        if message_id and new_status:
            await inbox_service.update_message_status(message_id, new_status)
            logger.info(f"Updated message {message_id} status to {new_status}")
            
    except Exception as e:
        logger.error(f"Error processing status update: {e}")