"""
WebSocket protocol definitions for frontend-to-backend communication.

Defines message types exchanged between the browser client and backend services.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """WebSocket message types for frontend communication."""

    # Client -> Server
    AUDIO = "audio"
    CONTROL = "control"

    # Server -> Client
    TRANSCRIPT = "transcript"
    PHASE_CHANGED = "phase_changed"
    SLOTS_SNAPSHOT = "slots_snapshot"
    TOOL_CALL = "tool_call"
    HANDOFF_STATUS = "handoff_status"
    SESSION_END = "session_end"
    ERROR = "error"


class AudioMessage(BaseModel):
    """Audio data message from client to server."""

    type: Literal[MessageType.AUDIO] = MessageType.AUDIO
    audio: str  # Base64-encoded PCM16 audio
    timestamp: Optional[datetime] = None


class ControlMessage(BaseModel):
    """Control message from client."""

    type: Literal[MessageType.CONTROL] = MessageType.CONTROL
    action: str  # "start", "stop", "mute", "unmute", "end"
    params: Optional[Dict[str, Any]] = None


class TranscriptMessage(BaseModel):
    """Transcript message to client."""

    type: Literal[MessageType.TRANSCRIPT] = MessageType.TRANSCRIPT
    role: str  # "user" or "assistant"
    text: str
    is_final: bool = True
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class PhaseChangedMessage(BaseModel):
    """Phase transition notification to client."""

    type: Literal[MessageType.PHASE_CHANGED] = MessageType.PHASE_CHANGED
    from_phase: Optional[str] = Field(None, alias="from")
    to_phase: str = Field(..., alias="to")
    trigger: str  # What triggered the phase change
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class SlotInfo(BaseModel):
    """Information about a single slot."""

    name: str
    status: str  # "pending", "filled", "invalid"
    value: Optional[Any] = None
    required: bool = False
    error: Optional[str] = None


class SlotsSnapshotMessage(BaseModel):
    """Snapshot of all slots in current phase."""

    type: Literal[MessageType.SLOTS_SNAPSHOT] = MessageType.SLOTS_SNAPSHOT
    phase: str
    slots: List[SlotInfo]
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class ToolCallMessage(BaseModel):
    """Tool call notification to client."""

    type: Literal[MessageType.TOOL_CALL] = MessageType.TOOL_CALL
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str
    status: str  # "started", "completed", "failed"
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class HandoffStatusMessage(BaseModel):
    """Handoff status notification to client."""

    type: Literal[MessageType.HANDOFF_STATUS] = MessageType.HANDOFF_STATUS
    status: str  # "initiated", "connecting", "connected", "failed"
    target_desk: str  # "faultdesk", "billingdesk", etc.
    message: Optional[str] = None
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class SessionEndMessage(BaseModel):
    """Session end notification to client."""

    type: Literal[MessageType.SESSION_END] = MessageType.SESSION_END
    reason: str  # "normal", "error", "timeout", "handoff"
    message: Optional[str] = None
    call_log_id: Optional[str] = None
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class ErrorMessage(BaseModel):
    """Error notification to client."""

    type: Literal[MessageType.ERROR] = MessageType.ERROR
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


# Union type for all frontend messages
FrontendMessage = Union[
    AudioMessage,
    ControlMessage,
    TranscriptMessage,
    PhaseChangedMessage,
    SlotsSnapshotMessage,
    ToolCallMessage,
    HandoffStatusMessage,
    SessionEndMessage,
    ErrorMessage,
]


def parse_frontend_message(data: Dict[str, Any]) -> FrontendMessage:
    """
    Parse a frontend WebSocket message.

    Args:
        data: Message data dictionary

    Returns:
        Parsed message object

    Raises:
        ValueError: If message type is unknown
    """
    msg_type = data.get("type")

    message_map = {
        MessageType.AUDIO: AudioMessage,
        MessageType.CONTROL: ControlMessage,
        MessageType.TRANSCRIPT: TranscriptMessage,
        MessageType.PHASE_CHANGED: PhaseChangedMessage,
        MessageType.SLOTS_SNAPSHOT: SlotsSnapshotMessage,
        MessageType.TOOL_CALL: ToolCallMessage,
        MessageType.HANDOFF_STATUS: HandoffStatusMessage,
        MessageType.SESSION_END: SessionEndMessage,
        MessageType.ERROR: ErrorMessage,
    }

    message_class = message_map.get(msg_type)

    if message_class is None:
        raise ValueError(f"Unknown message type: {msg_type}")

    return message_class(**data)
