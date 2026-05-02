"""
Frontdesk FastAPI application.

Main entry point for the frontdesk triage and routing service.
"""

import logging
import uuid
import asyncio
import base64
import json
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import jsonlogger
from voiceshared.ws_protocol.frontend import ErrorMessage

from app.config import config
from app.handoff import HandoffManager
from app.triage import register_triage_tools
from app.triage.instructions import get_triage_instructions
from voiceshared.tools import execute_tool, get_tool_schemas

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


def _event_type(event: Any) -> str:
    """Return a Voice Live event type as its wire string."""
    event_type = getattr(event, "type", "")
    return getattr(event_type, "value", event_type)


def _audio_delta_to_base64(delta: Any) -> str:
    if isinstance(delta, bytes):
        return base64.b64encode(delta).decode("ascii")
    if isinstance(delta, bytearray):
        return base64.b64encode(bytes(delta)).decode("ascii")
    return str(delta)


def _looks_like_internal_json(text: str) -> bool:
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return False
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and {"summary", "caller_attrs"}.issubset(data.keys())


def _is_startup_noise(transcript: str, started_at: datetime) -> bool:
    text = transcript.strip().rstrip("。.").lower()
    elapsed = (datetime.utcnow() - started_at).total_seconds()
    return elapsed < 5 and text in {"xbox, bing", "xbox bing", "x box, bing", "x box bing"}


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
            "voice_live_model": config.voice_live_model,
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
        "voice_session": None,
        "voice_event_task": None,
    }
    active_sessions[call_id] = session

    try:
        from voiceshared.voicelive import create_voice_session

        async def initiate_fault_handoff(
            triage_summary: str,
            caller_attrs: Dict[str, Any] | None = None,
        ) -> bool:
            if session.get("handoff_manager") and session["handoff_manager"].active:
                return True

            logger.info("Initiating automatic fault handoff for call %s: %s", call_id, triage_summary)
            handoff_mgr = HandoffManager(call_id, websocket)
            session["handoff_manager"] = handoff_mgr
            session["phase"] = "handoff_initiating"

            await websocket.send_json(
                {
                    "type": "handoff_status",
                    "status": "initiating",
                    "target_desk": "fault",
                    "message": "故障窓口におつなぎしています",
                }
            )

            success = await handoff_mgr.initiate_handoff(
                desk_name="fault",
                triage_summary=triage_summary,
                caller_attrs=caller_attrs or {},
            )

            if success:
                voice_event_task = session.get("voice_event_task")
                if voice_event_task and voice_event_task is not asyncio.current_task():
                    voice_event_task.cancel()

                voice_session_to_close = session.get("voice_session")
                session["voice_session"] = None
                if voice_session_to_close:
                    await voice_session_to_close.close()

                logger.info("Handoff successful for call %s", call_id)
                session["phase"] = "handoff"
                return True

            logger.error("Handoff failed for call %s", call_id)
            session["phase"] = "triage"
            session["handoff_manager"] = None
            await handoff_mgr.close()
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "HANDOFF_FAILED",
                    "message": "申し訳ございません。接続に失敗しました。",
                }
            )
            return False

        async def forward_voice_events() -> None:
            voice_session = session.get("voice_session")
            if voice_session is None:
                return

            async for event in voice_session.events():
                event_type = _event_type(event)
                logger.debug("Voice Live event for %s: %s", call_id, event_type)

                if event_type == "session.updated":
                    logger.info("Voice Live session ready for call %s", call_id)

                elif event_type == "input_audio_buffer.speech_started":
                    await websocket.send_json({"type": "speech_started"})

                elif event_type == "input_audio_buffer.speech_stopped":
                    await websocket.send_json({"type": "speech_stopped"})

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = getattr(event, "transcript", "")
                    if transcript:
                        if _is_startup_noise(transcript, session["started_at"]):
                            logger.info("Ignored startup transcript noise for %s: %s", call_id, transcript)
                            continue
                        logger.info("Transcript[%s] user: %s", call_id, transcript)
                        await websocket.send_json(
                            {
                                "type": "transcript",
                                "role": "user",
                                "text": transcript,
                                "is_final": True,
                            }
                        )

                elif event_type == "response.audio.delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        await websocket.send_json(
                            {
                                "type": "audio",
                                "audio": _audio_delta_to_base64(delta),
                            }
                        )

                elif event_type in {"response.text.done", "response.audio_transcript.done"}:
                    text = getattr(event, "text", None) or getattr(event, "transcript", "")
                    if text:
                        if _looks_like_internal_json(text):
                            logger.info("Suppressed internal JSON assistant transcript for %s", call_id)
                            continue
                        logger.info("Transcript[%s] assistant: %s", call_id, text)
                        await websocket.send_json(
                            {
                                "type": "transcript",
                                "role": "assistant",
                                "text": text,
                                "is_final": True,
                            }
                        )

                elif event_type == "response.function_call_arguments.done":
                    tool_name = getattr(event, "name", "")
                    tool_call_id = getattr(event, "call_id", "")
                    arguments_text = getattr(event, "arguments", "{}") or "{}"
                    try:
                        arguments = json.loads(arguments_text)
                    except json.JSONDecodeError:
                        arguments = {}

                    logger.info(
                        "Voice tool call[%s]: %s %s",
                        call_id,
                        tool_name,
                        arguments,
                    )
                    await websocket.send_json(
                        {
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "call_id": tool_call_id,
                            "status": "started",
                        }
                    )

                    if tool_name == "route_to_fault_desk":
                        result = await execute_tool(tool_name, arguments)
                        await websocket.send_json(
                            {
                                "type": "tool_call",
                                "tool_name": tool_name,
                                "arguments": arguments,
                                "call_id": tool_call_id,
                                "status": "completed" if result.get("success") else "failed",
                                "result": result.get("result"),
                                "error": result.get("error"),
                            }
                        )
                        await initiate_fault_handoff(
                            triage_summary=arguments.get("summary", "故障に関するお問い合わせ"),
                            caller_attrs=arguments.get("caller_attrs") or {},
                        )
                        break

                    result = await execute_tool(tool_name, arguments)
                    await websocket.send_json(
                        {
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "call_id": tool_call_id,
                            "status": "completed" if result.get("success") else "failed",
                            "result": result.get("result"),
                            "error": result.get("error"),
                        }
                    )
                    await voice_session.send_tool_result(tool_call_id, result)

                elif event_type == "error":
                    error = getattr(event, "error", None)
                    message = getattr(error, "message", "Voice Live error")
                    logger.error("Voice Live error for %s: %s", call_id, message)
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "VOICE_LIVE_ERROR",
                            "message": message,
                        }
                    )

        voice_session = await create_voice_session(
            endpoint=config.voice_live_endpoint,
            api_key=config.voice_live_api_key,
            instructions=get_triage_instructions(),
            tools=get_tool_schemas(),
            voice=config.voice_name,
            model=config.voice_live_model,
            temperature=config.voice_temperature,
            turn_detection={
                "threshold": config.turn_detection_threshold,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
                "create_response": True,
                "interrupt_response": True,
                "auto_truncate": True,
            },
        )
        session["voice_session"] = voice_session
        session["voice_event_task"] = asyncio.create_task(forward_voice_events())
        await voice_session.session.response.create(
            additional_instructions="最初の発話として『お電話ありがとうございます。本日はどのようなご用件でしょうか？』だけを自然に話してください。"
        )

        while True:
            # Receive message from browser
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "audio":
                logger.debug(f"Received audio frame from browser: {call_id}")

                handoff_manager = session.get("handoff_manager")
                if handoff_manager:
                    await handoff_manager.forward_from_browser(data)
                    continue

                active_voice_session = session.get("voice_session")
                audio = data.get("audio")
                if audio and active_voice_session:
                    await active_voice_session.send_audio(audio)

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
                await initiate_fault_handoff(
                    triage_summary=data.get("summary", "インターネット故障"),
                    caller_attrs=data.get("caller_attrs", {}),
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

            if session.get("voice_event_task"):
                session["voice_event_task"].cancel()

            if session.get("voice_session"):
                await session["voice_session"].close()

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
