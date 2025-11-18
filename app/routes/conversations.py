from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List
from app.services.inbox import InboxService
from app.schemas.conversation import ConversationListResponse, ConversationOut
from app.utils.logger import logger

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    archived: bool = Query(False),
    inbox_service: InboxService = Depends()
):
    """Get all conversations"""
    try:
        conversations = await inbox_service.get_conversations(limit, skip, archived)
        
        
        conversation_list = []
        for conv in conversations:
            conversation_list.append(ConversationOut(
                user_id=conv["user_id"],
                user_name=conv.get("user_name"),
                last_message=conv["last_message"],
                last_message_timestamp=conv["last_message_timestamp"],
                last_message_direction=conv["last_message_direction"],
                unread_count=conv["unread_count"],
                total_messages=conv["total_messages"],
                is_archived=conv["is_archived"],
                labels=conv.get("labels", []),
                created_at=conv["created_at"],
                updated_at=conv["updated_at"]
            ))
        
        total = await inbox_service.get_conversation_count(archived)
        pages = (total + limit - 1) // limit
        current_page = (skip // limit) + 1
        
        return ConversationListResponse(
            conversations=conversation_list,
            total=total,
            page=current_page,
            pages=pages,
            has_next=current_page < pages,
            has_prev=current_page > 1
        )
        
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")

@router.post("/{user_id}/mark-read")
async def mark_conversation_read(
    user_id: str,
    inbox_service: InboxService = Depends()
):
    """Mark all messages in conversation as read"""
    try:
        success = await inbox_service.mark_conversation_read(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"success": True, "message": "Conversation marked as read"}
        
    except Exception as e:
        logger.error(f"Error marking conversation as read: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark conversation as read")