import requests
import json
import time
from typing import Dict, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import *
from app.utils.logger import logger


class WhatsAppService:
    """WhatsApp Business API service"""
    
    def __init__(self):
        self.access_token = WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = WHATSAPP_PHONE_NUMBER_ID
        self.base_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Simple in-memory rate limiting (for now)
        self._last_request_time = 0
        self._request_count = 0
        self._rate_limit_window = 1.0  # 1 second
        self._max_requests_per_window = 80
    
    async def _check_rate_limit(self) -> bool:
        """Simple rate limiter"""
        current_time = time.time()
        
        # Reset counter if window has passed
        if current_time - self._last_request_time > self._rate_limit_window:
            self._request_count = 0
            self._last_request_time = current_time
        
        # Check if we're within limits
        if self._request_count >= self._max_requests_per_window:
            wait_time = self._rate_limit_window - (current_time - self._last_request_time)
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.2f}s")
                time.sleep(wait_time)
                self._request_count = 0
                self._last_request_time = time.time()
        
        self._request_count += 1
        return True
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError
        ))
    )
    async def send_text_message(self, to: str, message: str) -> Dict:
        """Send text message with retry logic"""
        
        # Wait for rate limit
        await self._check_rate_limit()
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.normalize_phone_number(to),
            "type": "text",
            "text": {"body": message}
        }
        
        return await self._make_request(payload)
    
    async def send_template_message(self, to: str, template_name: str, 
                                  parameters: List[Dict] = None,
                                  language_code: str = "en_US") -> Dict:
        """Send template message"""
        
        await self._check_rate_limit()
        
        template_data = {
            "name": template_name,
            "language": {"code": language_code}
        }
        
        if parameters:
            template_data["components"] = [{
                "type": "body",
                "parameters": parameters
            }]
        
        payload = {
            "messaging_product": "whatsapp",
            "to": self.normalize_phone_number(to),
            "type": "template",
            "template": template_data
        }
        
        return await self._make_request(payload)
    
    async def send_media_message(self, to: str, media_type: str, 
                               media_url: str = None, media_id: str = None,
                               caption: str = None) -> Dict:
        """Send media message (image, video, audio, document)"""
        
        await self._check_rate_limit()
        
        if not media_url and not media_id:
            return {
                "success": False,
                "error": "Either media_url or media_id must be provided"
            }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": self.normalize_phone_number(to),
            "type": media_type
        }
        
        media_obj = {"link" if media_url else "id": media_url or media_id}
        if caption and media_type in ["image", "video", "document"]:
            media_obj["caption"] = caption
        
        payload[media_type] = media_obj
        
        return await self._make_request(payload)
    
    async def mark_message_as_read(self, message_id: str) -> bool:
        """Mark message as read"""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to mark message as read: {e}")
            return False
    
    async def _make_request(self, payload: Dict) -> Dict:
        """Make API request to WhatsApp Business API"""
        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited by API. Retrying after {retry_after} seconds")
                time.sleep(retry_after)
                raise requests.exceptions.RetryError("Rate limited")
            
            response_data = response.json()
            
            if response.status_code == 200:
                message_id = response_data.get("messages", [{}])[0].get("id")
                logger.info(f"Message sent successfully, ID: {message_id}")
                return {
                    "success": True,
                    "message_id": message_id,
                    "error": None
                }
            else:
                error = response_data.get("error", {})
                error_msg = error.get("message", "Unknown error")
                error_code = error.get("code")
                
                logger.error(f"API error {error_code}: {error_msg}")
                return {
                    "success": False,
                    "message_id": None,
                    "error": error_msg,
                    "error_code": error_code
                }
                
        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            return {
                "success": False,
                "message_id": None,
                "error": "Request timeout"
            }
        except requests.exceptions.ConnectionError:
            logger.error("Connection error")
            return {
                "success": False,
                "message_id": None,
                "error": "Connection error"
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return {
                "success": False,
                "message_id": None,
                "error": str(e)
            }
    
    def normalize_phone_number(self, phone: str) -> str:
        """Normalize phone number for WhatsApp API"""
        # Remove all non-digit characters
        cleaned = ''.join(filter(str.isdigit, phone))
        
        # Ensure it has country code
        if len(cleaned) == 10:  # Assume India if no country code
            cleaned = '91' + cleaned
        
        return cleaned
    
    def validate_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Validate webhook signature from Meta"""
        import hmac
        import hashlib
        
        if not signature or not WHATSAPP_APP_SECRET:
            logger.warning("Missing signature or app secret for validation")
            return True  # Skip validation if not configured
        
        try:
            expected_signature = hmac.new(
                WHATSAPP_APP_SECRET.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(f"sha256={expected_signature}", signature)
        except Exception as e:
            logger.error(f"Error validating signature: {e}")
            return False