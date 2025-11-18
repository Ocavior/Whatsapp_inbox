from datetime import datetime, timedelta
from app.database.mongodb import db
from app.utils.logger import logger

class MongoDBRateLimiter:
    """Rate limiter using MongoDB"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def acquire(self, key: str) -> bool:
        """Check if request is allowed within rate limit"""
        try:
            window_start = datetime.utcnow().replace(microsecond=0)
            
            
            await self._clean_old_entries()
            
        
            result = await db.db.rate_limits.find_one_and_update(
                {
                    "key": key,
                    "window_start": window_start
                },
                {
                    "$inc": {"count": 1},
                    "$setOnInsert": {
                        "window_start": window_start,
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True,
                return_document=True
            )
            
            return result["count"] <= self.max_requests
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            return True  # Fail open
    
    async def _clean_old_entries(self):
        """Clean entries older than the window"""
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.window_seconds)
        await db.db.rate_limits.delete_many({
            "window_start": {"$lt": cutoff_time}
        })
    
    async def setup_ttl_index(self):
        """Create TTL index for automatic cleanup"""
        try:
            await db.db.rate_limits.create_index(
                [("created_at", 1)],
                expireAfterSeconds=self.window_seconds
            )
            logger.info("✅ TTL index created for rate limits")
        except Exception as e:
            logger.warning(f"Could not create TTL index: {e}")