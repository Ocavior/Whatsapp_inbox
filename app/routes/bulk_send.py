from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel, Field, validator
from app.services.bulk_sender import BulkMessageSender
from app.services.whatsapp import WhatsAppService
from app.utils.logger import logger

router = APIRouter(prefix="/api/bulk", tags=["bulk"])

# Create service instances at module level
whatsapp_service = WhatsAppService()
bulk_sender = BulkMessageSender(whatsapp_service)


class Contact(BaseModel):
    """Contact model for bulk sending"""
    phone: str = Field(..., description="Phone number with country code (e.g., 919876543210)")
    name: str = Field(..., description="Contact name for personalization")
    
    @validator('phone')
    def validate_phone(cls, v):
        # Remove spaces and special characters
        cleaned = ''.join(filter(str.isdigit, v))
        if len(cleaned) < 10:
            raise ValueError('Phone number must have at least 10 digits')
        return cleaned
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()


class BulkSendRequest(BaseModel):
    """Request model for bulk message sending"""
    message_template: str = Field(
        ..., 
        description="Message template with {name} placeholder. Example: 'Hello {name}, welcome!'",
        min_length=1,
        max_length=4096
    )
    contacts: List[Contact] = Field(
        ..., 
        description="List of contacts with phone and name",
        min_items=1,
        max_items=1000
    )
    delay: float = Field(
        default=1.0,
        description="Delay between messages in seconds",
        ge=0.5,
        le=5.0
    )
    
    @validator('message_template')
    def validate_template(cls, v):
        if '{name}' not in v:
            raise ValueError('Message template must contain {name} placeholder')
        return v


class BulkSendResponse(BaseModel):
    """Response model for bulk send"""
    total: int
    successful: int
    failed: int
    success_rate: float
    successful_contacts: List[dict]
    failed_contacts: List[dict]


@router.post("/send", response_model=BulkSendResponse)
async def send_bulk_messages(request: BulkSendRequest):
    """
    Send bulk WhatsApp messages with personalization
    
    **Request Body:**
    ```json
    {
      "message_template": "Hello {name}, we have a special offer for you!",
      "contacts": [
        {"phone": "919876543210", "name": "Rahul Kumar"},
        {"phone": "919123456789", "name": "Priya Sharma"}
      ],
      "delay": 1.5
    }
    ```
    
    **Response:**
    ```json
    {
      "total": 2,
      "successful": 2,
      "failed": 0,
      "success_rate": 100.0,
      "successful_contacts": [
        {"phone": "919876543210", "name": "Rahul Kumar"},
        {"phone": "919123456789", "name": "Priya Sharma"}
      ],
      "failed_contacts": []
    }
    ```
    
    **Message Personalization:**
    - Template: "Hello {name}, welcome!"
    - Sent to Rahul: "Hello Rahul Kumar, welcome!"
    - Sent to Priya: "Hello Priya Sharma, welcome!"
    """
    
    try:
        logger.info(f"Bulk send request: {len(request.contacts)} contacts")
        
        # Validate contacts
        validation = bulk_sender.validate_contacts(
            [c.dict() for c in request.contacts]
        )
        
        if validation['total_invalid'] > 0:
            logger.warning(f"Found {validation['total_invalid']} invalid contacts")
        
        # If all contacts are invalid, return error
        if validation['total_valid'] == 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "All contacts are invalid",
                    "invalid_contacts": validation['invalid']
                }
            )
        
        # Send messages
        result = await bulk_sender.send_bulk_messages(
            message_template=request.message_template,
            contacts=validation['valid'],
            delay=request.delay
        )
        
        return result
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Bulk send error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send bulk messages")


@router.post("/validate")
async def validate_contacts_endpoint(contacts: List[Contact]):
    """
    Validate contacts before sending (optional, for frontend pre-validation)
    
    **Request Body:**
    ```json
    {
      "contacts": [
        {"phone": "919876543210", "name": "Rahul"},
        {"phone": "123", "name": "Invalid"}
      ]
    }
    ```
    
    **Response:**
    ```json
    {
      "valid": [
        {"phone": "919876543210", "name": "Rahul"}
      ],
      "invalid": [
        {
          "phone": "123",
          "name": "Invalid",
          "row": 2,
          "error": "Invalid phone number (too short: 3 digits)"
        }
      ],
      "total_valid": 1,
      "total_invalid": 1
    }
    ```
    """
    try:
        validation = bulk_sender.validate_contacts([c.dict() for c in contacts])
        return validation
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail="Validation failed")


@router.get("/campaigns")
async def get_campaigns():
    """
    Get list of bulk message campaigns
    
    Note: Campaign tracking has been simplified in the new approach.
    This endpoint is available for future implementation if needed.
    """
    return {
        "message": "Campaign history endpoint - available for future implementation",
        "note": "New simplified approach focuses on direct message sending without campaign tracking"
    }