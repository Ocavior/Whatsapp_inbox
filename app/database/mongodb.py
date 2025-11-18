# app/database/mongodb.py
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()


class MongoDB:
    """MongoDB connection manager with both sync and async support"""
    
    def __init__(self):
        self.sync_client = None
        self.async_client = None
        self.db = None
        self.async_db = None
        self.MONGODB_URI = os.getenv("MONGODB_URI")
        self.DB_NAME = os.getenv("DATABASE_NAME", "whatsapp_business")
        
        if not self.MONGODB_URI:
            raise ValueError("❌ MONGODB_URI environment variable is not set")
    
    def connect(self):
        """Establish synchronous database connection"""
        try:
            # Synchronous client for immediate operations
            self.sync_client = MongoClient(self.MONGODB_URI)
            
            # Test the connection
            self.sync_client.admin.command('ping')
            self.db = self.sync_client[self.DB_NAME]
            
            print(f"✅ Successfully connected to MongoDB (sync): {self.DB_NAME}")
            return self.db
            
        except Exception as e:
            print(f"❌ Failed to connect to MongoDB: {e}")
            raise e
    
    async def connect_async(self):
        """Establish async database connection for FastAPI"""
        try:
            # Async client for FastAPI operations
            self.async_client = AsyncIOMotorClient(self.MONGODB_URI)
            
            # Test the connection
            await self.async_client.admin.command('ping')
            self.async_db = self.async_client[self.DB_NAME]
            
            print(f"✅ Successfully connected to MongoDB (async): {self.DB_NAME}")
            return self.async_db
            
        except Exception as e:
            print(f"❌ Failed to connect to MongoDB async: {e}")
            raise e
    
    def close(self):
        """Close synchronous connection"""
        if self.sync_client:
            self.sync_client.close()
            print("🔌 MongoDB sync connection closed")
    
    async def close_async(self):
        """Close async connection"""
        if self.async_client:
            self.async_client.close()
            print("🔌 MongoDB async connection closed")
    
    def get_database(self):
        """Get sync database instance"""
        if not self.db:
            self.connect()
        return self.db
    
    def get_async_database(self):
        """Get async database instance"""
        return self.async_db


# Create a global instance
db = MongoDB()