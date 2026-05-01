"""
Call log management for recording conversation details.

Maintains a structured log of the entire conversation including:
- Utterances (user and assistant)
- Phase transitions
- Slot updates
- Tool calls and results
- Timestamps
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CallLog:
    """
    Call log for tracking conversation details.

    This is separate from Voice Live's internal context and provides
    a complete audit trail for analytics and debugging.
    """

    def __init__(self, call_id: str):
        """
        Initialize call log.

        Args:
            call_id: Call identifier
        """
        self.call_id = call_id
        self.started_at = datetime.utcnow()
        self.ended_at: Optional[datetime] = None

        self.utterances: List[Dict] = []
        self.phase_transitions: List[Dict] = []
        self.tool_calls: List[Dict] = []
        self.slot_updates: List[Dict] = []
        self.metadata: Dict = {}

    def add_utterance(
        self, role: str, text: str, timestamp: Optional[datetime] = None
    ):
        """
        Add utterance to log.

        Args:
            role: Speaker role (user, assistant, system)
            text: Utterance text
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        self.utterances.append({
            "timestamp": timestamp.isoformat(),
            "role": role,
            "text": text,
        })

        logger.debug(f"CallLog[{self.call_id}]: Added {role} utterance")

    def add_phase_transition(
        self,
        from_phase: Optional[str],
        to_phase: str,
        trigger: str,
        timestamp: Optional[datetime] = None,
    ):
        """
        Record phase transition.

        Args:
            from_phase: Previous phase (None if initial)
            to_phase: New phase
            trigger: What triggered the transition
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        self.phase_transitions.append({
            "timestamp": timestamp.isoformat(),
            "from": from_phase,
            "to": to_phase,
            "trigger": trigger,
        })

        logger.info(f"CallLog[{self.call_id}]: Phase {from_phase} -> {to_phase}")

    def add_tool_call(
        self,
        tool_name: str,
        arguments: Dict,
        result: Optional[Dict] = None,
        timestamp: Optional[datetime] = None,
    ):
        """
        Record tool call.

        Args:
            tool_name: Name of tool called
            arguments: Tool arguments
            result: Optional tool result
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        self.tool_calls.append({
            "timestamp": timestamp.isoformat(),
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
        })

        logger.debug(f"CallLog[{self.call_id}]: Tool call {tool_name}")

    def add_slot_update(
        self,
        phase: str,
        slot_name: str,
        value: any,
        timestamp: Optional[datetime] = None,
    ):
        """
        Record slot update.

        Args:
            phase: Phase where slot was updated
            slot_name: Slot name
            value: New value
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        self.slot_updates.append({
            "timestamp": timestamp.isoformat(),
            "phase": phase,
            "slot": slot_name,
            "value": value,
        })

        logger.debug(f"CallLog[{self.call_id}]: Slot update {phase}.{slot_name}")

    def end_call(self, timestamp: Optional[datetime] = None):
        """
        Mark call as ended.

        Args:
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        self.ended_at = timestamp
        logger.info(f"CallLog[{self.call_id}]: Call ended")

    def export(self) -> Dict:
        """
        Export call log as dictionary.

        Returns:
            Complete call log data
        """
        return {
            "call_id": self.call_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": (
                (self.ended_at - self.started_at).total_seconds()
                if self.ended_at
                else None
            ),
            "utterances": self.utterances,
            "phase_transitions": self.phase_transitions,
            "tool_calls": self.tool_calls,
            "slot_updates": self.slot_updates,
            "metadata": self.metadata,
            "stats": {
                "total_utterances": len(self.utterances),
                "user_utterances": sum(
                    1 for u in self.utterances if u["role"] == "user"
                ),
                "assistant_utterances": sum(
                    1 for u in self.utterances if u["role"] == "assistant"
                ),
                "phase_transitions": len(self.phase_transitions),
                "tool_calls": len(self.tool_calls),
                "slot_updates": len(self.slot_updates),
            },
        }
