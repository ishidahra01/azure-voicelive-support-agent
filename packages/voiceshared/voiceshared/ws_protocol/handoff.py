"""
WebSocket protocol definitions for service-to-service handoff.

Defines message types exchanged between frontdesk and backend desk services
(e.g., faultdesk, billingdesk) during handoff operations.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class HandoffMessageType(str, Enum):
    """WebSocket message types for handoff communication."""

    # Frontdesk -> Desk
    HANDOFF_INIT = "handoff_init"
    AUDIO = "audio"
    CONTROL = "control"

    # Desk -> Frontdesk
    HANDOFF_ACK = "handoff_ack"
    TRANSCRIPT = "transcript"
    PHASE_CHANGED = "phase_changed"
    SLOTS_SNAPSHOT = "slots_snapshot"
    TOOL_CALL = "tool_call"
    SESSION_END = "session_end"
    ERROR = "error"


class HandoffInitMessage(BaseModel):
    """Initial handoff message from frontdesk to desk service."""

    type: str = Field(default=HandoffMessageType.HANDOFF_INIT, const=True)
    call_id: str
    triage_summary: str  # Summary of what the customer wants
    caller_attrs: Dict[str, Any]  # Caller attributes (phone number, area code, etc.)
    source_phase: str  # Phase in frontdesk before handoff (usually "triage")
    context: Optional[Dict[str, Any]] = None  # Additional context
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class HandoffAckMessage(BaseModel):
    """Acknowledgment from desk service that handoff was received."""

    type: str = Field(default=HandoffMessageType.HANDOFF_ACK, const=True)
    ready: bool
    desk_session_id: str
    message: Optional[str] = None
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class HandoffAudioMessage(BaseModel):
    """Audio data message in handoff protocol."""

    type: str = Field(default=HandoffMessageType.AUDIO, const=True)
    audio: str  # Base64-encoded PCM16 audio
    direction: str  # "upstream" (to desk) or "downstream" (from desk)
    timestamp: Optional[datetime] = None


class HandoffControlMessage(BaseModel):
    """Control message in handoff protocol."""

    type: str = Field(default=HandoffMessageType.CONTROL, const=True)
    action: str  # "pause", "resume", "end"
    params: Optional[Dict[str, Any]] = None


class HandoffTranscriptMessage(BaseModel):
    """Transcript message from desk to frontdesk."""

    type: str = Field(default=HandoffMessageType.TRANSCRIPT, const=True)
    role: str  # "user" or "assistant"
    text: str
    is_final: bool = True
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class HandoffPhaseChangedMessage(BaseModel):
    """Phase change notification from desk to frontdesk."""

    type: str = Field(default=HandoffMessageType.PHASE_CHANGED, const=True)
    from_phase: Optional[str] = Field(None, alias="from")
    to_phase: str = Field(..., alias="to")
    trigger: str
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class HandoffSlotInfo(BaseModel):
    """Slot information in handoff protocol."""

    name: str
    status: str  # "pending", "filled", "invalid"
    value: Optional[Any] = None
    required: bool = False


class HandoffSlotsSnapshotMessage(BaseModel):
    """Slots snapshot from desk to frontdesk."""

    type: str = Field(default=HandoffMessageType.SLOTS_SNAPSHOT, const=True)
    phase: str
    slots: List[HandoffSlotInfo]
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class HandoffToolCallMessage(BaseModel):
    """Tool call notification from desk to frontdesk."""

    type: str = Field(default=HandoffMessageType.TOOL_CALL, const=True)
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str
    status: str  # "started", "completed", "failed"
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class HandoffSessionEndMessage(BaseModel):
    """Session end notification from desk to frontdesk."""

    type: str = Field(default=HandoffMessageType.SESSION_END, const=True)
    reason: str  # "normal", "error", "escalate"
    message: Optional[str] = None
    return_to_frontdesk: bool = False  # If True, return control to frontdesk
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class HandoffErrorMessage(BaseModel):
    """Error notification in handoff protocol."""

    type: str = Field(default=HandoffMessageType.ERROR, const=True)
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


# Union type for all handoff messages
HandoffMessage = Union[
    HandoffInitMessage,
    HandoffAckMessage,
    HandoffAudioMessage,
    HandoffControlMessage,
    HandoffTranscriptMessage,
    HandoffPhaseChangedMessage,
    HandoffSlotsSnapshotMessage,
    HandoffToolCallMessage,
    HandoffSessionEndMessage,
    HandoffErrorMessage,
]


def parse_handoff_message(data: Dict[str, Any]) -> HandoffMessage:
    """
    Parse a handoff WebSocket message.

    Args:
        data: Message data dictionary

    Returns:
        Parsed message object

    Raises:
        ValueError: If message type is unknown
    """
    msg_type = data.get("type")

    message_map = {
        HandoffMessageType.HANDOFF_INIT: HandoffInitMessage,
        HandoffMessageType.HANDOFF_ACK: HandoffAckMessage,
        HandoffMessageType.AUDIO: HandoffAudioMessage,
        HandoffMessageType.CONTROL: HandoffControlMessage,
        HandoffMessageType.TRANSCRIPT: HandoffTranscriptMessage,
        HandoffMessageType.PHASE_CHANGED: HandoffPhaseChangedMessage,
        HandoffMessageType.SLOTS_SNAPSHOT: HandoffSlotsSnapshotMessage,
        HandoffMessageType.TOOL_CALL: HandoffToolCallMessage,
        HandoffMessageType.SESSION_END: HandoffSessionEndMessage,
        HandoffMessageType.ERROR: HandoffErrorMessage,
    }

    message_class = message_map.get(msg_type)

    if message_class is None:
        raise ValueError(f"Unknown handoff message type: {msg_type}")

    return message_class(**data)
