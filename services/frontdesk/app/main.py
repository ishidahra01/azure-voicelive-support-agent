"""
Frontdesk FastAPI application.

Main entry point for the frontdesk triage and routing service.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import jsonlogger
from voiceshared.ws_protocol.frontend import ErrorMessage

from app.config import config
from app.handoff import HandoffManager
from app.triage import register_triage_tools

# Configure logging
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
log_handler.setFormatter(formatter)
logging.root.addHandler(log_handler)
logging.root.setLevel(config.log_level)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Frontdesk Service",
    description="Triage and routing service for Azure Voice Live Support Agent",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register triage tools at startup
register_triage_tools()

# Store active sessions
active_sessions: Dict[str, Dict] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Frontdesk service starting up")
    logger.info(f"Voice Live endpoint: {config.voice_live_endpoint}")
    logger.info(f"Fault desk URL: {config.fault_desk_ws_url}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Frontdesk service shutting down")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "frontdesk",
        "status": "healthy",
        "version": "0.1.0",
        "active_sessions": len(active_sessions),
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "voice_name": config.voice_name,
            "model": config.azure_openai_model,
        },
    }


@app.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for browser connections.

    Handles:
    - Voice Live session creation
    - Triage conversation
    - Handoff to desk services
    - Audio streaming
    """
    await websocket.accept()

    call_id = str(uuid.uuid4())
    logger.info(f"New WebSocket connection: {call_id}")

    # Initialize session state
    session = {
        "call_id": call_id,
        "started_at": datetime.utcnow(),
        "phase": "triage",
        "handoff_manager": None,
    }
    active_sessions[call_id] = session

    try:
        # Send initial greeting
        await websocket.send_json(
            {
                "type": "transcript",
                "role": "assistant",
                "text": "お電話ありがとうございます。本日はどのようなご用件でしょうか？",
                "is_final": True,
            }
        )

        # Note: In a real implementation, we would:
        # 1. Create Voice Live session with triage instructions
        # 2. Handle audio frames from browser
        # 3. Process Voice Live events
        # 4. Execute tools when called
        # 5. Trigger handoff when route_to_*_desk is called

        # For this demonstration, we'll handle basic WebSocket messages
        while True:
            # Receive message from browser
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "audio":
                # Audio frame from browser
                # In real impl: forward to Voice Live
                logger.debug(f"Received audio frame from browser: {call_id}")

                if session.get("handoff_manager") and session["handoff_manager"].active:
                    await session["handoff_manager"].forward_from_browser(data)

            elif msg_type == "control":
                action = data.get("action")
                logger.info(f"Control action: {action} for call {call_id}")

                if session.get("handoff_manager") and session["handoff_manager"].active:
                    await session["handoff_manager"].forward_from_browser(data)

                if action == "end":
                    # End call
                    await websocket.send_json(
                        {
                            "type": "session_end",
                            "reason": "normal",
                            "message": "お電話ありがとうございました",
                        }
                    )
                    break

            # Demo: Simulate tool call detection
            # In real impl, Voice Live would call tools
            elif msg_type == "demo_route_fault":
                # Simulate routing to fault desk
                logger.info(f"Demo: Routing to fault desk for call {call_id}")

                # Create handoff manager
                handoff_mgr = HandoffManager(call_id, websocket)
                session["handoff_manager"] = handoff_mgr

                # Send handoff status
                await websocket.send_json(
                    {
                        "type": "handoff_status",
                        "status": "initiating",
                        "target_desk": "fault",
                        "message": "故障窓口におつなぎしています",
                    }
                )

                # Initiate handoff
                success = await handoff_mgr.initiate_handoff(
                    desk_name="fault",
                    triage_summary=data.get("summary", "インターネット故障"),
                    caller_attrs=data.get("caller_attrs", {}),
                )

                if success:
                    logger.info(f"Handoff successful for call {call_id}")
                    session["phase"] = "handoff"
                else:
                    logger.error(f"Handoff failed for call {call_id}")
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "HANDOFF_FAILED",
                            "message": "申し訳ございません。接続に失敗しました。",
                        }
                    )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {call_id}")

    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}", exc_info=True)
        try:
            error_msg = ErrorMessage(
                code="INTERNAL_ERROR",
                message="システムエラーが発生しました",
            )
            await websocket.send_json(error_msg.model_dump())
        except Exception:
            pass

    finally:
        # Cleanup
        if call_id in active_sessions:
            session = active_sessions[call_id]

            # Close handoff manager if active
            if session.get("handoff_manager"):
                await session["handoff_manager"].close()

            # Remove from active sessions
            del active_sessions[call_id]

        logger.info(f"Session ended: {call_id}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        reload=True,
    )
