"""
Phase state management.

Tracks current phase and phase transition history.
"""

import logging
from datetime import datetime
from typing import List, Optional

from app.phases import can_transition, get_next_phase, is_valid_phase

logger = logging.getLogger(__name__)


class PhaseTransition:
    """Record of a phase transition."""

    def __init__(
        self,
        from_phase: Optional[str],
        to_phase: str,
        trigger: str,
        timestamp: Optional[datetime] = None,
    ):
        self.from_phase = from_phase
        self.to_phase = to_phase
        self.trigger = trigger
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "from": self.from_phase,
            "to": self.to_phase,
            "trigger": self.trigger,
            "timestamp": self.timestamp.isoformat(),
        }


class PhaseState:
    """
    Manages current phase and transition history.
    """

    def __init__(self, call_id: str, initial_phase: str = "intake"):
        self.call_id = call_id
        self.current = initial_phase
        self.previous: Optional[str] = None
        self.history: List[PhaseTransition] = []

        # Record initial phase
        self.history.append(
            PhaseTransition(
                from_phase=None,
                to_phase=initial_phase,
                trigger="handoff_init",
            )
        )

        logger.info(f"PhaseState initialized for call {call_id}: {initial_phase}")

    def transition_to(self, target_phase: str, trigger: str) -> bool:
        """
        Transition to a new phase.

        Args:
            target_phase: Target phase name
            trigger: What triggered this transition

        Returns:
            True if transition successful
        """
        # Validate target phase
        if not is_valid_phase(target_phase):
            logger.error(f"Invalid phase: {target_phase}")
            return False

        # Check if transition is allowed
        if not can_transition(self.current, target_phase):
            logger.warning(f"Transition not allowed: {self.current} -> {target_phase}")
            return False

        # Record transition
        transition = PhaseTransition(
            from_phase=self.current,
            to_phase=target_phase,
            trigger=trigger,
        )
        self.history.append(transition)

        # Update state
        self.previous = self.current
        self.current = target_phase

        logger.info(f"Phase transition: {self.previous} -> {self.current} ({trigger})")

        return True

    def auto_progress(self) -> Optional[str]:
        """
        Automatically progress to next phase.

        Returns:
            Next phase name if progressed, None otherwise
        """
        next_phase = get_next_phase(self.current)

        if next_phase:
            if self.transition_to(next_phase, trigger="auto_progression"):
                return next_phase

        return None

    def get_transition_history(self) -> List[dict]:
        """Get transition history as list of dicts."""
        return [t.to_dict() for t in self.history]

    def export(self):
        """Export phase state."""
        return {
            "call_id": self.call_id,
            "current_phase": self.current,
            "previous_phase": self.previous,
            "history": self.get_transition_history(),
        }
