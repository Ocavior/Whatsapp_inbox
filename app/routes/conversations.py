from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
from app.services.inbox import InboxService
from app.utils.logger import logger
from app.database.mongodb import db

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
inbox_service = InboxService()

@router.get("/debug")
async def debug_conversations():
    try:
        database = db.async_db
        message_count = await database.messages.count_documents({})
        conversation_count = await database.conversations.count_documents({})
        sample_messages = await database.messages.find().limit(5).to_list(5)
        sample_conversations = await database.conversations.find().limit(5).to_list(5)
        pipeline = [{"$group": {"_id": "$user_id"}}, {"$limit": 10}]
        unique_users = await database.messages.aggregate(pipeline).to_list(10)
        return {
            "message_count": message_count,
            "conversation_count": conversation_count,
            "unique_user_ids": [u["_id"] for u in unique_users],
            "sample_messages": [
                {
                    "user_id": m.get("user_id"),
                    "direction": m.get("direction"),
                    "body": m.get("body", "")[:50],
                    "timestamp": m.get("timestamp")
                } for m in sample_messages
            ],
            "sample_conversations": [
                {
                    "user_id": c.get("user_id"),
                    "last_message": c.get("last_message", "")[:50],
                    "total_messages": c.get("total_messages"),
                    "unread_count": c.get("unread_count")
                } for c in sample_conversations
            ]
        }
    except Exception as e:
        logger.error(f"Debug error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync")
async def sync_conversations():
    try:
        database = db.async_db
        pipeline = [
            {"$group": {
                "_id": "$user_id",
                "last_message": {"$last": "$body"},
                "last_timestamp": {"$last": "$timestamp"},
                "last_direction": {"$last": "$direction"},
                "total": {"$sum": 1},
                "unread": {
                    "$sum": {
                        "$cond": [
                            {"$and": [
                                {"$eq": ["$direction", "inbound"]},
                                {"$ne": ["$status", "read"]}
                            ]},
                            1,
                            0
                        ]
                    }
                }
            }},
            {"$sort": {"last_timestamp": -1}}
        ]
        user_stats = await database.messages.aggregate(pipeline).to_list(None)
        synced_count = 0
        for stat in user_stats:
            user_id = stat["_id"]
            await database.conversations.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "last_message": stat.get("last_message", "")[:500],
                        "last_message_timestamp": stat.get("last_timestamp"),
                        "last_message_direction": stat.get("last_direction"),
                        "total_messages": stat.get("total", 0),
                        "unread_count": stat.get("unread", 0),
                        "updated_at": datetime.utcnow(),
                        "is_archived": False
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow(),
                        "labels": []
                    }
                },
                upsert=True
            )
            synced_count += 1
        logger.info(f"Synced {synced_count} conversations")
        return {
            "success": True,
            "synced_count": synced_count,
            "message": f"Successfully synced {synced_count} conversations"
        }
    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("")
async def get_conversations(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    archived: bool = Query(False)
):
    try:
        conversations = await inbox_service.get_conversations(limit, skip, archived)
        total = await inbox_service.get_conversation_count(archived)
        logger.info(f"Fetched {len(conversations)} conversations (total: {total})")
        return {
            "conversations": conversations,
            "total": total,
            "limit": limit,
            "skip": skip
        }
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/messages")
async def get_conversation_messages(
    user_id: str,
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    days: Optional[int] = Query(None, ge=1, le=365)
):
    try:
        messages = await inbox_service.get_messages_with_date_filter(
            user_id, limit, skip, days
        )
        total = await inbox_service.get_message_count(user_id, days)
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
        logger.error(f"Error fetching messages for {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/history")
async def get_conversation_history(
    user_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=1000)
):
    try:
        start_dt = None
        end_dt = None
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        messages = await inbox_service.get_messages_by_date_range(
            user_id, start_dt, end_dt, limit
        )
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
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error fetching history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{user_id}/read")
async def mark_conversation_read(user_id: str):
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
    try:
        results = await inbox_service.search_messages(query, user_id, limit)
        return {
            "query": query,
            "user_id": user_id,
            "total": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"Error searching messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/stats")
async def get_conversation_stats(user_id: str):
    try:
        stats = await inbox_service.get_conversation_stats(user_id)
        return stats
    except Exception as e:
        logger.error(f"Error fetching stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
