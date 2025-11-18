import asyncio
import csv
from datetime import datetime
from typing import List, Dict, Optional, Callable
from bson import ObjectId
from app.database.mongodb import db
from app.services.whatsapp import WhatsAppService
from app.utils.logger import logger


class BulkMessageSender:
    """Service for sending bulk messages"""
    
    def __init__(self, whatsapp_service: WhatsAppService):
        self.whatsapp_service = whatsapp_service
    
    def _get_db(self):
        """Get database instance"""
        if db.async_db is None:
            raise RuntimeError("Database not connected")
        return db.async_db
    
    async def send_bulk_messages(self, contacts: List[Dict], message_template: str,
                               campaign_name: str, delay: float = 1.0,
                               progress_callback: Optional[Callable] = None) -> Dict:
        """Send bulk messages with progress tracking"""
        
        campaign_id = ObjectId()
        total = len(contacts)
        successful = []
        failed = []
        
        
        await self._create_campaign(campaign_id, campaign_name, total)
        
        for index, contact in enumerate(contacts, 1):
            try:
                phone = contact.get('phone', '').strip()
                if not phone:
                    logger.warning(f"Skipping contact {index}: No phone number")
                    failed.append({
                        **contact,
                        "error": "No phone number"
                    })
                    continue
                
                
                message = self._personalize_message(message_template, contact)
                
                
                result = await self.whatsapp_service.send_text_message(phone, message)
                
                database = self._get_db()
                
                
                if result['success']:
                    message_data = {
                        "user_id": phone,
                        "direction": "outbound",
                        "message_type": "text",
                        "body": message,
                        "timestamp": datetime.utcnow(),
                        "status": "sent",
                        "message_id": result['message_id'],
                        "campaign_id": str(campaign_id),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                    
                    await database.messages.insert_one(message_data)
                    successful.append(contact)
                    
                else:
                    
                    message_data = {
                        "user_id": phone,
                        "direction": "outbound",
                        "message_type": "text",
                        "body": message,
                        "timestamp": datetime.utcnow(),
                        "status": "failed",
                        "error_reason": result.get('error', 'Unknown error'),
                        "campaign_id": str(campaign_id),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                    
                    await database.messages.insert_one(message_data)
                    failed.append({
                        **contact,
                        "error": result.get('error', 'Unknown error')
                    })
                
                
                if progress_callback:
                    progress_callback(index, total, len(successful), len(failed))
                
                
                if index < total:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error processing contact {index}: {e}", exc_info=True)
                failed.append({
                    **contact,
                    "error": str(e)
                })
        
        
        await self._update_campaign(campaign_id, len(successful), len(failed))
        
        return {
            "campaign_id": str(campaign_id),
            "campaign_name": campaign_name,
            "total": total,
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": (len(successful) / total * 100) if total > 0 else 0,
            "successful_contacts": successful[:10],  
            "failed_contacts": failed[:10] 
        }
    
    async def load_contacts_from_csv(self, csv_file_path: str) -> List[Dict]:
        """Load contacts from CSV file"""
        contacts = []
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    
                    contacts.append({k.strip(): v.strip() for k, v in row.items()})
            
            logger.info(f"Loaded {len(contacts)} contacts from {csv_file_path}")
            return contacts
            
        except Exception as e:
            logger.error(f"Error loading CSV file: {e}", exc_info=True)
            raise
    
    def validate_contacts(self, contacts: List[Dict]) -> Dict:
        """Validate contact list"""
        valid_contacts = []
        invalid_contacts = []
        
        for idx, contact in enumerate(contacts, 1):
            phone = contact.get('phone', '').strip()
            
            if not phone:
                invalid_contacts.append({
                    **contact,
                    "row": idx,
                    "error": "Missing phone number"
                })
                continue
            
            
            cleaned_phone = ''.join(filter(str.isdigit, phone))
            if len(cleaned_phone) < 10:
                invalid_contacts.append({
                    **contact,
                    "row": idx,
                    "error": f"Invalid phone number (too short: {len(cleaned_phone)} digits)"
                })
                continue
            
            valid_contacts.append(contact)
        
        return {
            "valid": valid_contacts,
            "invalid": invalid_contacts,
            "total_valid": len(valid_contacts),
            "total_invalid": len(invalid_contacts)
        }
    
    def _personalize_message(self, template: str, contact: Dict) -> str:
        """Personalize message with contact data"""
        try:
            
            return template.format(**contact)
        except KeyError as e:
            logger.warning(f"Missing placeholder {e} in template, using original template")
            return template
        except Exception as e:
            logger.error(f"Error personalizing message: {e}")
            return template
    
    async def _create_campaign(self, campaign_id: ObjectId, name: str, total_contacts: int):
        """Create campaign record"""
        try:
            database = self._get_db()
            await database.campaigns.insert_one({
                "_id": campaign_id,
                "name": name,
                "total_contacts": total_contacts,
                "successful_count": 0,
                "failed_count": 0,
                "status": "running",
                "created_at": datetime.utcnow(),
                "started_at": datetime.utcnow()
            })
            logger.info(f"Campaign created: {name} (ID: {campaign_id})")
        except Exception as e:
            logger.error(f"Error creating campaign: {e}", exc_info=True)
    
    async def _update_campaign(self, campaign_id: ObjectId, successful: int, failed: int):
        """Update campaign completion status"""
        try:
            database = self._get_db()
            total = successful + failed
            status = "completed" if total > 0 else "failed"
            
            await database.campaigns.update_one(
                {"_id": campaign_id},
                {
                    "$set": {
                        "status": status,
                        "successful_count": successful,
                        "failed_count": failed,
                        "completed_at": datetime.utcnow(),
                        "success_rate": (successful / total * 100) if total > 0 else 0
                    }
                }
            )
            logger.info(f"Campaign {campaign_id} completed: {successful} success, {failed} failed")
        except Exception as e:
            logger.error(f"Error updating campaign: {e}", exc_info=True)
    
    async def get_campaign_status(self, campaign_id: str) -> Optional[Dict]:
        """Get campaign status"""
        try:
            database = self._get_db()
            campaign = await database.campaigns.find_one({"_id": ObjectId(campaign_id)})
            if campaign:
                campaign['_id'] = str(campaign['_id'])
                return campaign
            return None
        except Exception as e:
            logger.error(f"Error getting campaign status: {e}")
            return None