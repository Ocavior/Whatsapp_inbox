import asyncio
from datetime import datetime
from typing import List, Dict
from bson import ObjectId
from app.database.mongodb import db
from app.services.whatsapp import WhatsAppService
from app.utils.logger import logger


class BulkMessageSender:
    """Service for sending bulk messages - Simplified JSON approach"""
    
    def __init__(self, whatsapp_service: WhatsAppService):
        self.whatsapp_service = whatsapp_service
    
    def _get_db(self):
        """Get database instance"""
        if db.async_db is None:
            raise RuntimeError("Database not connected")
        return db.async_db
    
    async def send_bulk_messages(self, message_template: str, contacts: List[Dict],
                                delay: float = 1.0) -> Dict:
        """
        Send bulk messages with simplified approach
        
        Args:
            message_template: Template with {name} placeholder
            contacts: List of {"phone": "919876543210", "name": "John"}
            delay: Delay between messages in seconds
        """
        
        total = len(contacts)
        successful = []
        failed = []
        
        logger.info(f"Starting bulk send: {total} contacts")
        
        for index, contact in enumerate(contacts, 1):
            try:
                phone = contact.get('phone', '').strip()
                name = contact.get('name', '').strip()
                
                # Validate phone number
                if not phone:
                    logger.warning(f"Skipping contact {index}: No phone number")
                    failed.append({
                        "phone": phone or "N/A",
                        "name": name or "N/A",
                        "error": "Phone number is required"
                    })
                    continue
                
                # Personalize message by replacing {name}
                personalized_message = message_template.replace('{name}', name if name else 'Customer')
                
                # Send message
                logger.info(f"Sending to {phone} ({index}/{total})")
                result = await self.whatsapp_service.send_text_message(phone, personalized_message)
                
                database = self._get_db()
                
                # Save message to database
                if result['success']:
                    message_data = {
                        "user_id": phone,
                        "direction": "outbound",
                        "message_type": "text",
                        "body": personalized_message,
                        "timestamp": datetime.utcnow(),
                        "status": "sent",
                        "message_id": result['message_id'],
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                    
                    await database.messages.insert_one(message_data)
                    successful.append({
                        "phone": phone,
                        "name": name
                    })
                    logger.info(f"✅ Success: {phone}")
                    
                else:
                    # Save failed message
                    message_data = {
                        "user_id": phone,
                        "direction": "outbound",
                        "message_type": "text",
                        "body": personalized_message,
                        "timestamp": datetime.utcnow(),
                        "status": "failed",
                        "error_reason": result.get('error', 'Unknown error'),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                    
                    await database.messages.insert_one(message_data)
                    failed.append({
                        "phone": phone,
                        "name": name,
                        "error": result.get('error', 'Unknown error')
                    })
                    logger.error(f"❌ Failed: {phone} - {result.get('error')}")
                
                # Delay between messages (except last one)
                if index < total:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error processing contact {index}: {e}", exc_info=True)
                failed.append({
                    "phone": contact.get('phone', 'N/A'),
                    "name": contact.get('name', 'N/A'),
                    "error": str(e)
                })
        
        # Calculate results
        success_rate = (len(successful) / total * 100) if total > 0 else 0
        
        logger.info(f"Bulk send completed: {len(successful)}/{total} successful ({success_rate:.1f}%)")
        
        return {
            "total": total,
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": round(success_rate, 2),
            "successful_contacts": successful,
            "failed_contacts": failed
        }
    
    def validate_contacts(self, contacts: List[Dict]) -> Dict:
        """Validate contact list before sending"""
        valid_contacts = []
        invalid_contacts = []
        
        for idx, contact in enumerate(contacts, 1):
            phone = contact.get('phone', '').strip()
            name = contact.get('name', '').strip()
            
            # Check phone number exists
            if not phone:
                invalid_contacts.append({
                    "phone": "N/A",
                    "name": name,
                    "row": idx,
                    "error": "Phone number is required"
                })
                continue
            
            # Basic phone validation - at least 10 digits
            cleaned_phone = ''.join(filter(str.isdigit, phone))
            if len(cleaned_phone) < 10:
                invalid_contacts.append({
                    "phone": phone,
                    "name": name,
                    "row": idx,
                    "error": f"Invalid phone number (too short: {len(cleaned_phone)} digits)"
                })
                continue
            
            # Valid contact
            valid_contacts.append(contact)
        
        return {
            "valid": valid_contacts,
            "invalid": invalid_contacts,
            "total_valid": len(valid_contacts),
            "total_invalid": len(invalid_contacts)
        }