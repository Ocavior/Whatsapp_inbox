from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from app.config import *
from app.database.mongodb import db
from app.utils.logger import logger
from app.routes import webhook, messages, conversations, bulk_send
from datetime import datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager"""
    # Startup
    logger.info("🚀 WhatsApp Business API starting up...")
    
    try:
        # Connect to MongoDB (async)
        await db.connect_async()
        logger.info("✅ Database connected successfully")
        
        # Initialize any other startup tasks here
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    
    finally:
        # Shutdown
        logger.info("👋 WhatsApp Business API shutting down...")
        await db.close_async()


app = FastAPI(
    title="WhatsApp Business API",
    description="Production-ready WhatsApp Bulk Message Sender & Inbox",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(webhook.router)
app.include_router(messages.router)
app.include_router(conversations.router)
app.include_router(bulk_send.router)


@app.get("/")
async def root():
    return {
        "message": "WhatsApp Business API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        if db.async_client:
            await db.async_client.admin.command('ping')
            return {
                "status": "healthy",
                "database": "connected",
                "database_name": db.DB_NAME,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "database": "disconnected",
                    "error": "Database client not initialized"
                }
            )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "error",
                "error": str(e)
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=DEBUG,
        log_level=LOG_LEVEL.lower()
    )