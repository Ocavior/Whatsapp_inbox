from datetime import datetime
from app.database.mongodb import db
import json
from datetime import datetime, timedelta

class MongoDBQueue:
    """Simple queue using MongoDB"""
    
    def __init__(self, queue_name: str):
        self.collection = db.db.queues
        self.queue_name = queue_name
    
    async def push(self, item):
        """Add item to queue"""
        await self.collection.insert_one({
            "queue": self.queue_name,
            "data": item,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "attempts": 0
        })
    
    async def pop(self):
        """Get and lock next item"""
        result = await self.collection.find_one_and_update(
            {
                "queue": self.queue_name,
                "status": "pending"
            },
            {
                "$set": {
                    "status": "processing",
                    "locked_at": datetime.utcnow()
                },
                "$inc": {"attempts": 1}
            },
            sort=[("created_at", 1)],  
            return_document=True 
        )
        return result
    
    async def complete(self, item_id, success: bool = True):
        """Mark item as completed"""
        await self.collection.update_one(
            {"_id": item_id},
            {
                "$set": {
                    "status": "completed" if success else "failed",
                    "completed_at": datetime.utcnow()
                }
            }
        )
    
    async def retry_failed(self, max_attempts: int = 3):
        """Reset failed items for retry"""
        await self.collection.update_many(
            {
                "queue": self.queue_name,
                "status": "failed",
                "attempts": {"$lt": max_attempts}
            },
            {
                "$set": {"status": "pending"}
            }
        )
    
    async def cleanup_old_items(self, hours_old: int = 24):
        """Clean up old completed/failed items"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
        await self.collection.delete_many({
            "status": {"$in": ["completed", "failed"]},
            "created_at": {"$lt": cutoff_time}
        })