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

@router.get("/conversation/{user_id}", response_model=MessageListResponse)
async def get_conversation(
    user_id: str,
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    inbox_service: InboxService = Depends()
):
    """Get conversation with a specific user"""
    try:
        messages = await inbox_service.get_user_messages(user_id, limit, skip)
        
        
        message_list = []
        for msg in messages:
            message_list.append(MessageOut(
                id=str(msg["_id"]),
                user_id=msg["user_id"],
                direction=msg["direction"],
                message_type=msg["message_type"],
                body=msg["body"],
                timestamp=msg["timestamp"],
                status=msg["status"],
                message_id=msg.get("message_id"),
                media_url=msg.get("media_url"),
                media_type=msg.get("media_type"),
                created_at=msg["created_at"],
                updated_at=msg["updated_at"]
            ))
        
        total = await inbox_service.get_message_count(user_id)
        pages = (total + limit - 1) // limit
        current_page = (skip // limit) + 1
        
        return MessageListResponse(
            messages=message_list,
            total=total,
            page=current_page,
            pages=pages,
            has_next=current_page < pages,
            has_prev=current_page > 1
        )
        
    except Exception as e:
        logger.error(f"Error fetching conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversation")

@router.get("/search", response_model=List[MessageOut])
async def search_messages(
    q: str = Query(..., min_length=1),
    user_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    inbox_service: InboxService = Depends()
):
    """Search messages by content"""
    try:
        messages = await inbox_service.search_messages(q, user_id, limit)
        
        result = []
        for msg in messages:
            result.append(MessageOut(
                id=str(msg["_id"]),
                user_id=msg["user_id"],
                direction=msg["direction"],
                message_type=msg["message_type"],
                body=msg["body"],
                timestamp=msg["timestamp"],
                status=msg["status"],
                message_id=msg.get("message_id"),
                created_at=msg["created_at"],
                updated_at=msg["updated_at"]
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to search messages")