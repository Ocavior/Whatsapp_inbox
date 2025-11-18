from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import tempfile
import os
from app.services.bulk_sender import BulkMessageSender
from app.services.whatsapp import WhatsAppService
from app.utils.logger import logger

router = APIRouter(prefix="/api/bulk", tags=["bulk"])

# Create service instances at module level
whatsapp_service = WhatsAppService()
bulk_sender = BulkMessageSender(whatsapp_service)

@router.post("/send")
async def send_bulk_messages(
    campaign_name: str = Form(..., description="Name for this campaign"),
    message_template: str = Form(..., description="Message template with {placeholders}"),
    contacts_file: UploadFile = File(..., description="CSV file with contacts"),
    delay: float = Form(1.0, ge=0.1, le=10.0, description="Delay between messages in seconds")
):
    """Send bulk messages from CSV file"""
    try:
    
        if not contacts_file.filename or not contacts_file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            content = await contacts_file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            
            contacts = await bulk_sender.load_contacts_from_csv(temp_path)
            
            
            validation_result = bulk_sender.validate_contacts(contacts)
            
            if validation_result["total_valid"] == 0:
                raise HTTPException(status_code=400, detail="No valid contacts found")
            
            
            result = await bulk_sender.send_bulk_messages(
                contacts=validation_result["valid"],
                message_template=message_template,
                campaign_name=campaign_name,
                delay=delay
            )
            
            result["validation"] = validation_result
            
            return result
            
        finally:
            
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk send: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/campaigns")
async def get_campaigns():
    """Get list of bulk message campaigns"""
    return {"message": "Campaign history endpoint - implement as needed"}