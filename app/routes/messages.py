from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from app.services.inbox import InboxService
from app.services.whatsapp import WhatsAppService
from datetime import datetime
from app.schemas.message import (
    SendMessageRequest, SendMessageResponse, MessageOut, MessageListResponse
)
from app.utils.logger import logger

router = APIRouter(prefix="/api/messages", tags=["messages"])

@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    inbox_service: InboxService = Depends(),
    whatsapp_service: WhatsAppService = Depends()
):
    """Send a message to a user"""
    try:
        
        if request.message_type == "text":
            result = await whatsapp_service.send_text_message(request.to, request.message)
        elif request.message_type == "template" and request.template_name:
            result = await whatsapp_service.send_template_message(
                request.to, request.template_name, request.template_params
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported message type")
        
    
        if result["success"]:
            message_data = {
                "user_id": request.to,
                "direction": "outbound",
                "message_type": request.message_type,
                "body": request.message,
                "timestamp": datetime.utcnow(),
                "status": "sent",
                "message_id": result["message_id"]
            }
            
            if request.template_name:
                message_data["template_name"] = request.template_name
                message_data["template_params"] = request.template_params
            
            await inbox_service.save_message(message_data)
        
        return SendMessageResponse(
            success=result["success"],
            message_id=result["message_id"],
            error=result["error"]
        )
        
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
