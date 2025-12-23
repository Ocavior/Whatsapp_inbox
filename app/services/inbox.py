from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from bson import ObjectId
from app.database.mongodb import db
from app.models.message import Message, MessageStatus, MessageDirection
from app.utils.logger import logger


class InboxService:
    """Service for managing messages and conversations"""
    
    def __init__(self):
        """Initialize service - db will be accessed when needed"""
        pass
    
    def _get_db(self):
        """Get database instance"""
        if db.async_db is None:
            raise RuntimeError("Database not connected. Ensure app startup completed.")
        return db.async_db
    
    async def save_message(self, message_data: Dict[str, Any]) -> Optional[str]:
        """Save message to database"""
        try:
            database = self._get_db()
            message = Message(**message_data)
            
            # Convert to dict and handle ObjectId
            message_dict = message.model_dump(by_alias=True, exclude_none=True)
            if '_id' in message_dict and message_dict['_id'] is None:
                del message_dict['_id']
            
            result = await database.messages.insert_one(message_dict)
            message_id = str(result.inserted_id)
            
            # Update conversation
            await self._update_conversation(message)
            
            logger.info(f"Message saved for user {message.user_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error saving message: {e}", exc_info=True)
            return None
    
    async def update_message_status(self, message_id: str, status: str, 
                                  error_reason: Optional[str] = None) -> bool:
        """Update message status (sent/delivered/read/failed)"""
        try:
            database = self._get_db()
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow()
            }
            
            if error_reason:
                update_data["error_reason"] = error_reason
            
            result = await database.messages.update_one(
                {"message_id": message_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"Message {message_id} status updated to {status}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating message status: {e}", exc_info=True)
            return False
    
    async def get_user_messages(self, user_id: str, limit: int = 100, 
                              skip: int = 0) -> List[Dict]:
        """Get messages for a specific user (BOTH inbound and outbound)"""
        try:
            database = self._get_db()
            cursor = database.messages.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).skip(skip).limit(limit)
            
            messages = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string
            for msg in messages:
                if '_id' in msg:
                    msg['_id'] = str(msg['_id'])
            
            return messages
            
        except Exception as e:
            logger.error(f"Error fetching messages for {user_id}: {e}", exc_info=True)
            return []
    
    async def get_messages_with_date_filter(self, user_id: str, limit: int = 100,
                                          skip: int = 0, days: Optional[int] = None) -> List[Dict]:
        """
        Get messages with optional date filter
        
        Args:
            user_id: Customer phone number
            limit: Number of messages
            skip: Pagination offset
            days: Get messages from last N days (e.g., 10, 15, 20)
        """
        try:
            database = self._get_db()
            
            # Build query
            query = {"user_id": user_id}
            
            # Add date filter if specified
            if days:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                query["timestamp"] = {"$gte": cutoff_date}
            
            # Get messages (both inbound and outbound)
            cursor = database.messages.find(query).sort("timestamp", -1).skip(skip).limit(limit)
            
            messages = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string
            for msg in messages:
                if '_id' in msg:
                    msg['_id'] = str(msg['_id'])
            
            logger.info(f"Fetched {len(messages)} messages for {user_id}" + 
                       (f" (last {days} days)" if days else ""))
            
            return messages
            
        except Exception as e:
            logger.error(f"Error fetching messages: {e}", exc_info=True)
            return []
    
    async def get_messages_by_date_range(self, user_id: str, 
                                        start_date: Optional[datetime] = None,
                                        end_date: Optional[datetime] = None,
                                        limit: int = 500) -> List[Dict]:
        """
        Get messages between specific dates
        
        Args:
            user_id: Customer phone number
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            limit: Max messages
        """
        try:
            database = self._get_db()
            
            # Build query
            query = {"user_id": user_id}
            
            # Add date range filter
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            
            if date_filter:
                query["timestamp"] = date_filter
            
            # Get messages
            cursor = database.messages.find(query).sort("timestamp", -1).limit(limit)
            
            messages = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string
            for msg in messages:
                if '_id' in msg:
                    msg['_id'] = str(msg['_id'])
            
            return messages
            
        except Exception as e:
            logger.error(f"Error fetching messages by date range: {e}", exc_info=True)
            return []
    
    async def get_message_count(self, user_id: str, days: Optional[int] = None) -> int:
        """Get total message count for user with optional date filter"""
        try:
            database = self._get_db()
            
            query = {"user_id": user_id}
            
            if days:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                query["timestamp"] = {"$gte": cutoff_date}
            
            count = await database.messages.count_documents(query)
            return count
        except Exception as e:
            logger.error(f"Error counting messages: {e}")
            return 0
    
    async def get_conversations(self, limit: int = 50, skip: int = 0, 
                              archived: bool = False) -> List[Dict]:
        """Get all conversations"""
        try:
            database = self._get_db()
            query = {"is_archived": archived}
            cursor = database.conversations.find(query).sort(
                "last_message_timestamp", -1
            ).skip(skip).limit(limit)
            
            conversations = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string
            for conv in conversations:
                if '_id' in conv:
                    conv['_id'] = str(conv['_id'])
            
            return conversations
            
        except Exception as e:
            logger.error(f"Error fetching conversations: {e}", exc_info=True)
            return []
    
    async def get_conversation_by_user_id(self, user_id: str) -> Optional[Dict]:
        """Get conversation metadata by user_id"""
        try:
            database = self._get_db()
            conversation = await database.conversations.find_one({"user_id": user_id})
            
            if conversation:
                conversation['_id'] = str(conversation['_id'])
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error fetching conversation: {e}")
            return None
    
    async def get_conversation_count(self, archived: bool = False) -> int:
        """Get total conversation count"""
        try:
            database = self._get_db()
            count = await database.conversations.count_documents({"is_archived": archived})
            return count
        except Exception as e:
            logger.error(f"Error counting conversations: {e}")
            return 0
    
    async def mark_conversation_read(self, user_id: str) -> bool:
        """Mark all messages in conversation as read"""
        try:
            database = self._get_db()
            result = await database.conversations.update_one(
                {"user_id": user_id},
                {"$set": {"unread_count": 0, "updated_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error marking conversation as read: {e}")
            return False
    
    async def search_messages(self, query: str, user_id: Optional[str] = None,
                            limit: int = 50) -> List[Dict]:
        """Search messages by content"""
        try:
            database = self._get_db()
            search_filter = {"body": {"$regex": query, "$options": "i"}}
            if user_id:
                search_filter["user_id"] = user_id
            
            cursor = database.messages.find(search_filter).sort(
                "timestamp", -1
            ).limit(limit)
            
            messages = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string
            for msg in messages:
                if '_id' in msg:
                    msg['_id'] = str(msg['_id'])
            
            return messages
            
        except Exception as e:
            logger.error(f"Error searching messages: {e}", exc_info=True)
            return []
    
    async def get_conversation_stats(self, user_id: str) -> Dict:
        """Get conversation statistics"""
        try:
            database = self._get_db()
            
            # Total messages
            total_messages = await database.messages.count_documents({"user_id": user_id})
            
            # Inbound messages
            inbound_count = await database.messages.count_documents({
                "user_id": user_id,
                "direction": "inbound"
            })
            
            # Outbound messages
            outbound_count = await database.messages.count_documents({
                "user_id": user_id,
                "direction": "outbound"
            })
            
            # First and last message dates
            first_message = await database.messages.find_one(
                {"user_id": user_id},
                sort=[("timestamp", 1)]
            )
            
            last_message = await database.messages.find_one(
                {"user_id": user_id},
                sort=[("timestamp", -1)]
            )
            
            # Message types breakdown
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {
                    "_id": "$message_type",
                    "count": {"$sum": 1}
                }}
            ]
            type_breakdown = await database.messages.aggregate(pipeline).to_list(None)
            
            return {
                "user_id": user_id,
                "total_messages": total_messages,
                "inbound_messages": inbound_count,
                "outbound_messages": outbound_count,
                "first_message_date": first_message.get("timestamp") if first_message else None,
                "last_message_date": last_message.get("timestamp") if last_message else None,
                "message_types": {item["_id"]: item["count"] for item in type_breakdown}
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            return {}
    
    async def _update_conversation(self, message: Message):
        """Update conversation when new message arrives"""
        try:
            database = self._get_db()
            
            update_ops = {
                "$set": {
                    "user_id": message.user_id,
                    "last_message": message.body[:500],
                    "last_message_timestamp": message.timestamp,
                    "last_message_direction": message.direction,
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow(),
                    "is_archived": False,
                    "labels": [],
                    "unread_count": 0,
                    "total_messages": 0
                }
            }
            
            # Increment counters
            if message.direction == MessageDirection.INBOUND:
                update_ops["$inc"] = {
                    "unread_count": 1,
                    "total_messages": 1
                }
            else:
                update_ops["$inc"] = {"total_messages": 1}
            
            await database.conversations.update_one(
                {"user_id": message.user_id},
                update_ops,
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Error updating conversation: {e}", exc_info=True)