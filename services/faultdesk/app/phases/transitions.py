"""
Phase transition rules.

Defines which phase transitions are allowed.
"""

from typing import Dict, Set

# Allowed transitions (all-to-all for maximum flexibility)
PHASE_TRANSITIONS: Dict[str, Set[str]] = {
    "intake": {"identity", "interview", "visit", "closing"},
    "identity": {"intake", "interview", "visit", "closing"},
    "interview": {"intake", "identity", "visit", "closing"},
    "visit": {"intake", "identity", "interview", "closing"},
    "closing": {"intake", "identity", "interview", "visit"},  # Allow reopening
}


def can_transition(from_phase: str, to_phase: str) -> bool:
    """
    Check if transition from one phase to another is allowed.

    Args:
        from_phase: Current phase
        to_phase: Target phase

    Returns:
        True if transition is allowed
    """
    if from_phase not in PHASE_TRANSITIONS:
        return False

    allowed_targets = PHASE_TRANSITIONS[from_phase]
    return to_phase in allowed_targets


def get_allowed_transitions(from_phase: str) -> Set[str]:
    """Get all allowed transitions from a phase."""
    return PHASE_TRANSITIONS.get(from_phase, set())
