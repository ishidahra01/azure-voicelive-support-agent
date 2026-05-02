"""
Faultdesk FastAPI application.

Main entry point for the faultdesk service with Phase+Slot management.
"""

import json
import logging
import uuid
import base64
import asyncio
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pythonjsonlogger import jsonlogger
from voiceshared.ws_protocol.handoff import HandoffInitMessage, parse_handoff_message
from voiceshared.tools import execute_tool, get_tool_schemas

from app.config import config
from app.orchestrator import PhaseState, generate_instructions
from app.orchestrator.tools import register_orchestrator_tools
from app.slots.schema import PHASE_SLOTS
from app.slots import SlotStore

# Configure logging
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
log_handler.setFormatter(formatter)
logging.root.addHandler(log_handler)
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


def _event_type(event: Any) -> str:
    event_type = getattr(event, "type", "")
    return getattr(event_type, "value", event_type)


def _audio_delta_to_base64(delta: Any) -> str:
    if isinstance(delta, bytes):
        return base64.b64encode(delta).decode("ascii")
    if isinstance(delta, bytearray):
        return base64.b64encode(bytes(delta)).decode("ascii")
    return str(delta)


def _slot_snapshot(phase: str, slot_store: SlotStore) -> list[dict[str, Any]]:
    slots = []
    for slot_def in PHASE_SLOTS.get(phase, []):
        value = slot_store.get(phase, slot_def.name)
        status = slot_store.get_status(phase, slot_def.name)
        slots.append(
            {
                "name": slot_def.name,
                "status": status.value if status else "pending",
                "value": value,
                "required": slot_def.required,
            }
        )
    return slots


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
            "voice_live_model": config.voice_live_model,
            "azure_openai_model": config.azure_openai_model,
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

        logger.info(f"Handoff received for call {call_id}: {triage_summary}")

        # Initialize session state. Frontdesk has already completed intake intent capture,
        # so faultdesk starts from identity while preserving intake as completed history.
        phase_state = PhaseState(call_id, initial_phase="identity")
        slot_store = SlotStore(call_id)
        slot_store.set("intake", "greeting_done", True)
        slot_store.set("intake", "understood_intent", True)
        if triage_summary:
            slot_store.set("interview", "fault_symptom", triage_summary)

        # Import context and tools
        from app.context import CallLog
        from app.orchestrator.tools import set_tool_context

        call_log = CallLog(call_id)

        # Set tool context for skill execution
        set_tool_context(call_id, slot_store, phase_state, call_log)

        session = {
            "call_id": call_id,
            "desk_session_id": desk_session_id,
            "started_at": datetime.utcnow(),
            "phase_state": phase_state,
            "slot_store": slot_store,
            "call_log": call_log,
            "triage_summary": triage_summary,
            "caller_attrs": caller_attrs,
        }
        active_sessions[call_id] = session

        # Send handoff_ack
        await websocket.send_json(
            {
                "type": "handoff_ack",
                "ready": True,
                "desk_session_id": desk_session_id,
                "message": "Faultdesk ready",
            }
        )

        logger.info(f"Sent handoff_ack for call {call_id}")

        # Generate initial instructions
        instructions = generate_instructions(
            phase_state, slot_store, handoff_summary=triage_summary
        )
        logger.debug(f"Initial instructions: {instructions[:200]}...")

        from voiceshared.voicelive import create_voice_session

        async def send_phase_if_changed(previous_phase: str) -> None:
            if phase_state.current == previous_phase:
                return
            call_log.add_phase_transition(
                phase_state.previous,
                phase_state.current,
                "tool_execution",
            )
            await websocket.send_json(
                {
                    "type": "phase_changed",
                    "from": phase_state.previous,
                    "to": phase_state.current,
                    "trigger": "tool_execution",
                }
            )

        async def send_slots_snapshot(phase: str | None = None) -> None:
            snapshot_phase = phase or phase_state.current
            await websocket.send_json(
                {
                    "type": "slots_snapshot",
                    "phase": snapshot_phase,
                    "slots": _slot_snapshot(snapshot_phase, slot_store),
                }
            )

        async def forward_voice_events() -> None:
            voice_session = session.get("voice_session")
            if voice_session is None:
                return

            async for event in voice_session.events():
                event_type = _event_type(event)
                logger.debug("Faultdesk Voice Live event for %s: %s", call_id, event_type)

                if event_type == "session.updated":
                    logger.info("Faultdesk Voice Live session ready for call %s", call_id)

                elif event_type == "input_audio_buffer.speech_started":
                    await websocket.send_json({"type": "speech_started"})

                elif event_type == "input_audio_buffer.speech_stopped":
                    await websocket.send_json({"type": "speech_stopped"})

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = getattr(event, "transcript", "")
                    if transcript:
                        logger.info("Transcript[%s] user: %s", call_id, transcript)
                        call_log.add_utterance("user", transcript)
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
                                "direction": "downstream",
                            }
                        )

                elif event_type in {"response.text.done", "response.audio_transcript.done"}:
                    text = getattr(event, "text", None) or getattr(event, "transcript", "")
                    if text:
                        logger.info("Transcript[%s] assistant: %s", call_id, text)
                        call_log.add_utterance("assistant", text)
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

                    previous_phase = phase_state.current
                    logger.info("Voice tool call[%s]: %s %s", call_id, tool_name, arguments)
                    await websocket.send_json(
                        {
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "call_id": tool_call_id,
                            "status": "started",
                        }
                    )

                    result = await execute_tool(tool_name, arguments)
                    call_log.add_tool_call(tool_name, arguments, result)
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

                    await send_phase_if_changed(previous_phase)
                    await send_slots_snapshot()

                    new_instructions = generate_instructions(
                        phase_state,
                        slot_store,
                        handoff_summary=triage_summary,
                    )
                    await voice_session.update_instructions(new_instructions)
                    await voice_session.send_tool_result(tool_call_id, result)

                elif event_type == "error":
                    error = getattr(event, "error", None)
                    message = getattr(error, "message", "Voice Live error")
                    logger.error("Faultdesk Voice Live error for %s: %s", call_id, message)
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
            instructions=instructions,
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

        # Send initial phase
        await websocket.send_json(
            {
                "type": "phase_changed",
                "from": None,
                "to": phase_state.current,
                "trigger": "handoff_init",
            }
        )
        call_log.add_phase_transition(None, phase_state.current, "handoff_init")

        # Send initial slots snapshot
        await send_slots_snapshot(phase_state.current)
        await voice_session.session.response.create(
            additional_instructions=(
                f"受付から『{triage_summary}』と引き継がれています。故障内容は既知として扱ってください。"
                "最初の発話として、故障窓口に切り替わったことを一文で伝え、"
                "手配確認のためのお客様番号だけを質問してください。"
                "『どのようなご用件でしょうか』や症状の再確認はしないでください。"
            )
        )

        # Handle messages from frontdesk
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "audio":
                # Audio frame from frontdesk/browser
                logger.debug(f"Received audio frame for call {call_id}")
                audio = data.get("audio")
                active_voice_session = session.get("voice_session")
                if audio and active_voice_session:
                    await active_voice_session.send_audio(audio)

            elif msg_type == "control":
                action = data.get("action")
                logger.info(f"Control action: {action} for call {call_id}")

                if action == "end":
                    # End session
                    await websocket.send_json(
                        {
                            "type": "session_end",
                            "reason": "normal",
                            "message": "対応完了",
                        }
                    )
                    break

            # Demo: Simulate phase progression
            elif msg_type == "demo_next_phase":
                # Progress to next phase
                next_phase = phase_state.auto_progress()
                if next_phase:
                    call_log.add_phase_transition(
                        phase_state.previous,
                        next_phase,
                        "auto_progression",
                    )
                    await websocket.send_json(
                        {
                            "type": "phase_changed",
                            "from": phase_state.previous,
                            "to": next_phase,
                            "trigger": "auto_progression",
                        }
                    )

                    # Send updated slots snapshot
                    await send_slots_snapshot(next_phase)

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
            call_log = session.get("call_log")

            if session.get("voice_event_task"):
                session["voice_event_task"].cancel()

            if session.get("voice_session"):
                await session["voice_session"].close()

            # End call log if it exists
            if call_log:
                call_log.end_call()

            # Export call log
            call_log_data = {
                "call_id": call_id,
                "desk_session_id": desk_session_id,
                "started_at": session["started_at"].isoformat(),
                "ended_at": datetime.utcnow().isoformat(),
                "triage_summary": session["triage_summary"],
                "phase_state": phase_state.export(),
                "slots": slot_store.export(),
            }

            # Add detailed call log if available
            if call_log:
                detailed_log = call_log.export()
                call_log_data["transcript"] = detailed_log["utterances"]
                call_log_data["detailed_log"] = detailed_log

            # Save to file
            log_file = config.call_logs_dir / f"{call_id}.json"
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(call_log_data, f, ensure_ascii=False, indent=2)

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
