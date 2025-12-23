from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta
from app.services.inbox import InboxService
from app.utils.logger import logger

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# Create service instance
inbox_service = InboxService()


@router.get("")
async def get_conversations(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    archived: bool = Query(False)
):
    """
    Get all conversations (inbox list)
    
    Returns list of conversations with last message, unread count, etc.
    """
    try:
        conversations = await inbox_service.get_conversations(limit, skip, archived)
        total = await inbox_service.get_conversation_count(archived)
        
        return {
            "conversations": conversations,
            "total": total,
            "limit": limit,
            "skip": skip
        }
        
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/messages")
async def get_conversation_messages(
    user_id: str,
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    days: Optional[int] = Query(None, ge=1, le=365, description="Get messages from last N days")
):
    """
    Get complete conversation history with a customer (both inbound and outbound)
    
    **Parameters:**
    - user_id: Customer phone number (e.g., 919876543210)
    - limit: Number of messages to fetch (default 100, max 500)
    - skip: Pagination offset
    - days: Optional - Get messages from last N days (e.g., 10, 15, 20)
    
    **Examples:**
    - Get last 100 messages: /api/conversations/919876543210/messages
    - Get last 10 days: /api/conversations/919876543210/messages?days=10
    - Get last 20 days: /api/conversations/919876543210/messages?days=20
    - Paginate: /api/conversations/919876543210/messages?limit=50&skip=50
    """
    try:
        # Get messages with optional date filter
        messages = await inbox_service.get_messages_with_date_filter(
            user_id, 
            limit, 
            skip,
            days
        )
        
        # Get total count
        total = await inbox_service.get_message_count(user_id, days)
        
        # Get conversation metadata
        conversation = await inbox_service.get_conversation_by_user_id(user_id)
        
        return {
            "user_id": user_id,
            "messages": messages,
            "total": total,
            "limit": limit,
            "skip": skip,
            "days_filter": days,
            "conversation": conversation
        }
        
    except Exception as e:
        logger.error(f"Error fetching messages for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/history")
async def get_conversation_history(
    user_id: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(500, ge=1, le=1000)
):
    """
    Get conversation history between specific dates
    
    **Examples:**
    - Last 10 days: /api/conversations/919876543210/history
    - Specific range: /api/conversations/919876543210/history?start_date=2025-11-01&end_date=2025-11-30
    """
    try:
        # Parse dates
        start_dt = None
        end_dt = None
        
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            # Set to end of day
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        
        # Get messages
        messages = await inbox_service.get_messages_by_date_range(
            user_id,
            start_dt,
            end_dt,
            limit
        )
        
        # Group by date for better display
        grouped_messages = {}
        for msg in messages:
            date_key = msg.get('timestamp', datetime.utcnow()).strftime('%Y-%m-%d')
            if date_key not in grouped_messages:
                grouped_messages[date_key] = []
            grouped_messages[date_key].append(msg)
        
        return {
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_messages": len(messages),
            "messages": messages,
            "grouped_by_date": grouped_messages
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{user_id}/read")
async def mark_conversation_read(user_id: str):
    """
    Mark all messages in conversation as read
    
    This updates the conversation's unread_count to 0
    """
    try:
        success = await inbox_service.mark_conversation_read(user_id)
        
        if success:
            return {
                "success": True,
                "user_id": user_id,
                "message": "Conversation marked as read"
            }
        else:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
    except Exception as e:
        logger.error(f"Error marking conversation as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_messages(
    query: str = Query(..., min_length=1),
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Search messages by content
    
    **Parameters:**
    - query: Search term
    - user_id: Optional - Search within specific conversation
    - limit: Max results
    """
    try:
        results = await inbox_service.search_messages(query, user_id, limit)
        
        return {
            "query": query,
            "user_id": user_id,
            "total": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/stats")
async def get_conversation_stats(user_id: str):
    """
    Get conversation statistics
    
    Returns message counts, response times, etc.
    """
    try:
        stats = await inbox_service.get_conversation_stats(user_id)
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))