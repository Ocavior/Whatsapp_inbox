# app/services/mongodb_cache.py
import time
from app.database.mongodb import *  

class MongoDBCache:
    def __init__(self):
        try:
            
            database = db.connect()  
            
            if database is None:
                raise Exception("Database connection failed - database is None")
            
            self.collection = database.cache
            print("✅ MongoDBCache initialized successfully")
            
        except Exception as e:
            print(f"❌ Error initializing MongoDBCache: {e}")
            raise e

    def get(self, key):
        try:
            if self.collection is None:
                return None
                
            doc = self.collection.find_one({"_id": key})
            return doc["value"] if doc and "value" in doc else None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None

    def set(self, key, value, ttl_seconds=3600):
        try:
            if self.collection is None:
                return
                
            self.collection.update_one(
                {"_id": key},
                {
                    "$set": {
                        "value": value,
                        "expires_at": time.time() + ttl_seconds
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"Cache set error: {e}")