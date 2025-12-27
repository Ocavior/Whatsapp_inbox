from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websockets.connection_manager import manager
from app.utils.logger import logger
from datetime import datetime

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/notifications")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time notifications
    
    Connect from frontend:
    const ws = new WebSocket('ws://localhost:8000/ws/notifications');
    """
    
    await manager.connect(websocket)
    
    try:
        # Send 
        await websocket.send_json({
            "type": "connected",
            "message": "Successfully connected to notification service",
            "timestamp": datetime.utcnow().isoformat(),
            "active_connections": manager.get_connection_count()
        })
        
        logger.info("📨 Sent welcome message to client")
        
        # Keep connection alive and handle client messages
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            logger.info(f"📥 Received from client: {data}")
            
            # Handle ping/pong for keepalive
            if data == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("👋 Client disconnected normally")
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


@router.get("/connections")
async def get_active_connections():
    """Get number of active WebSocket connections (for monitoring)"""
    return {
        "active_connections": manager.get_connection_count(),
        "timestamp": datetime.utcnow().isoformat()
    }