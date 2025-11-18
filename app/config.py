import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# WhatsApp Configuration
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "verify_token")

# Database
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "whatsapp_business")

# Application
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Rate Limiting
MAX_MESSAGES_PER_SECOND = int(os.getenv("MAX_MESSAGES_PER_SECOND", "80"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
MESSAGE_DELAY = float(os.getenv("MESSAGE_DELAY", "1.0"))

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# File Upload
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "52428800"))  # 50MB

# Validation - Check required variables
required_vars = {
    "WHATSAPP_ACCESS_TOKEN": WHATSAPP_ACCESS_TOKEN,
    "WHATSAPP_PHONE_NUMBER_ID": WHATSAPP_PHONE_NUMBER_ID,
    "MONGODB_URI": MONGODB_URI
}

missing_vars = [var for var, value in required_vars.items() if not value]

if missing_vars:
    error_msg = f"""
    ❌ Missing required environment variables: {', '.join(missing_vars)}
    
    Please create a .env file with the following variables:
    {chr(10).join(f'  - {var}' for var in missing_vars)}
    
    See .env.example for reference.
    """
    raise ValueError(error_msg)

# Security warnings
if DEBUG:
    print("⚠️  DEBUG mode is ON - DO NOT use in production!")

if SECRET_KEY == "your-secret-key-change-in-production":
    print("⚠️  Using default SECRET_KEY - CHANGE IT in production!")

print("✅ Configuration loaded successfully")