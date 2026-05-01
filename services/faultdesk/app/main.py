"""
Faultdesk FastAPI application.

Main entry point for the faultdesk service with Phase+Slot management.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pythonjsonlogger import jsonlogger
from voiceshared.tools import get_tool_schemas
from voiceshared.ws_protocol.handoff import HandoffInitMessage, parse_handoff_message

from app.config import config
from app.orchestrator import PhaseState, generate_instructions
from app.orchestrator.tools import register_orchestrator_tools
from app.slots import SlotStore

# Configure logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logging.root.addHandler(logHandler)
logging.root.setLevel(config.log_level)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Faultdesk Service",
    description="Fault handling desk with Phase+Slot conversation management",
    version="0.1.0",
)

# Register orchestrator tools at startup
register_orchestrator_tools()

# Store active sessions
active_sessions: Dict[str, Dict] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Faultdesk service starting up")
    logger.info(f"Voice Live endpoint: {config.voice_live_endpoint}")

    # Ensure call logs directory exists
    config.call_logs_dir.mkdir(parents=True, exist_ok=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Faultdesk service shutting down")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "faultdesk",
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


@app.websocket("/ws/desk")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for handoff from frontdesk.

    Handles:
    - Handoff initialization
    - Phase + Slot management
    - Voice Live orchestration
    - Skill execution
    """
    await websocket.accept()

    desk_session_id = str(uuid.uuid4())
    call_id: str = ""
    logger.info(f"New desk WebSocket connection: {desk_session_id}")

    try:
        # Wait for handoff_init message
        first_message = await websocket.receive_json()

        try:
            handoff_msg = parse_handoff_message(first_message)
        except Exception as e:
            logger.error(f"Invalid handoff message: {e}")
            await websocket.close(code=1002, reason="Invalid handoff message")
            return

        if not isinstance(handoff_msg, HandoffInitMessage):
            logger.error("Expected handoff_init message")
            await websocket.close(code=1002, reason="Expected handoff_init")
            return

        call_id = handoff_msg.call_id
        triage_summary = handoff_msg.triage_summary
        caller_attrs = handoff_msg.caller_attrs

        logger.info(
            f"Handoff received for call {call_id}: {triage_summary}"
        )

        # Initialize session state
        phase_state = PhaseState(call_id, initial_phase="intake")
        slot_store = SlotStore(call_id)

        session = {
            "call_id": call_id,
            "desk_session_id": desk_session_id,
            "started_at": datetime.utcnow(),
            "phase_state": phase_state,
            "slot_store": slot_store,
            "triage_summary": triage_summary,
            "caller_attrs": caller_attrs,
        }
        active_sessions[call_id] = session

        # Send handoff_ack
        await websocket.send_json({
            "type": "handoff_ack",
            "ready": True,
            "desk_session_id": desk_session_id,
            "message": "Faultdesk ready",
        })

        logger.info(f"Sent handoff_ack for call {call_id}")

        # Generate initial instructions
        instructions = generate_instructions(
            phase_state, slot_store, handoff_summary=triage_summary
        )
        logger.debug(f"Initial instructions: {instructions[:200]}...")

        # Note: In a real implementation, we would:
        # 1. Create Voice Live session with generated instructions
        # 2. Handle audio frames from frontdesk
        # 3. Process Voice Live events
        # 4. Execute tools when called
        # 5. Update phase_state and slot_store
        # 6. Send phase_changed and slots_snapshot messages
        # 7. Regenerate instructions on each turn

        # Send initial greeting
        await websocket.send_json({
            "type": "transcript",
            "role": "assistant",
            "text": f"承知いたしました。{triage_summary}の件ですね。担当させていただきます。",
            "is_final": True,
        })

        # Send initial phase
        await websocket.send_json({
            "type": "phase_changed",
            "from": None,
            "to": "intake",
            "trigger": "handoff_init",
        })

        # Send initial slots snapshot
        await websocket.send_json({
            "type": "slots_snapshot",
            "phase": "intake",
            "slots": [
                {"name": "greeting_done", "status": "pending", "required": True},
                {"name": "understood_intent", "status": "pending", "required": True},
            ],
        })

        # Handle messages from frontdesk
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "audio":
                # Audio frame from frontdesk/browser
                logger.debug(f"Received audio frame for call {call_id}")
                # In real impl: forward to Voice Live

            elif msg_type == "control":
                action = data.get("action")
                logger.info(f"Control action: {action} for call {call_id}")

                if action == "end":
                    # End session
                    await websocket.send_json({
                        "type": "session_end",
                        "reason": "normal",
                        "message": "対応完了",
                    })
                    break

            # Demo: Simulate phase progression
            elif msg_type == "demo_next_phase":
                # Progress to next phase
                next_phase = phase_state.auto_progress()
                if next_phase:
                    await websocket.send_json({
                        "type": "phase_changed",
                        "from": phase_state.previous,
                        "to": next_phase,
                        "trigger": "auto_progression",
                    })

                    # Send updated slots snapshot
                    pending_slots = slot_store.get_pending_slots(next_phase)
                    await websocket.send_json({
                        "type": "slots_snapshot",
                        "phase": next_phase,
                        "slots": [
                            {"name": s, "status": "pending", "required": True}
                            for s in pending_slots
                        ],
                    })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {desk_session_id}")

    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}", exc_info=True)

    finally:
        # Cleanup and export call log
        if call_id and call_id in active_sessions:
            session = active_sessions[call_id]
            phase_state = session["phase_state"]
            slot_store = session["slot_store"]

            # Export call log
            call_log = {
                "call_id": call_id,
                "desk_session_id": desk_session_id,
                "started_at": session["started_at"].isoformat(),
                "ended_at": datetime.utcnow().isoformat(),
                "triage_summary": session["triage_summary"],
                "phase_state": phase_state.export(),
                "slots": slot_store.export(),
            }

            # Save to file
            log_file = config.call_logs_dir / f"{call_id}.json"
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(call_log, f, ensure_ascii=False, indent=2)

            logger.info(f"Call log saved: {log_file}")

            # Remove from active sessions
            del active_sessions[call_id]

        logger.info(f"Session ended: {desk_session_id}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        reload=True,
    )
