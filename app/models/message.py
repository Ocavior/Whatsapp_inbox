from datetime import datetime
from typing import Optional, Literal
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    RECEIVED = "received"
    PENDING = "pending"


class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    TEMPLATE = "template"
    LOCATION = "location"
    CONTACTS = "contacts"


class Message(BaseModel):
    """Message model for MongoDB"""
    
    
    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="WhatsApp phone number")
    direction: MessageDirection
    message_type: MessageType = MessageType.TEXT
    body: str
    timestamp: datetime
    status: MessageStatus
    message_id: Optional[str] = Field(None, description="WhatsApp message ID")
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    media_id: Optional[str] = None
    template_name: Optional[str] = None
    template_params: Optional[dict] = None
    error_reason: Optional[str] = None
    retry_count: int = Field(default=0, ge=0)
    campaign_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class Conversation(BaseModel):
    """Conversation model for tracking user conversations"""
    
    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="WhatsApp phone number")
    user_name: Optional[str] = None
    last_message: str
    last_message_timestamp: datetime
    last_message_direction: MessageDirection
    unread_count: int = Field(default=0, ge=0)
    total_messages: int = Field(default=0, ge=0)
    is_archived: bool = False
    labels: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )