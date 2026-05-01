"""
Phase definitions.

Defines all conversation phases for the fault desk.
"""

from typing import Dict, List

from pydantic import BaseModel


class Phase(BaseModel):
    """Definition of a conversation phase."""

    name: str
    description: str
    next_phase: str = ""  # Default next phase (can be overridden)


# Phase definitions
PHASES: Dict[str, Phase] = {
    "intake": Phase(
        name="intake",
        description="受付・状況再確認",
        next_phase="identity",
    ),
    "identity": Phase(
        name="identity",
        description="本人確認",
        next_phase="interview",
    ),
    "interview": Phase(
        name="interview",
        description="故障状況聞き取り・診断",
        next_phase="visit",
    ),
    "visit": Phase(
        name="visit",
        description="訪問日程調整",
        next_phase="closing",
    ),
    "closing": Phase(
        name="closing",
        description="クロージング",
        next_phase="",  # End of conversation
    ),
}

# Phase order for linear progression
PHASE_ORDER: List[str] = ["intake", "identity", "interview", "visit", "closing"]


def get_next_phase(current_phase: str) -> str:
    """Get the next phase in the linear progression."""
    phase_def = PHASES.get(current_phase)
    return phase_def.next_phase if phase_def else ""


def get_phase_description(phase_name: str) -> str:
    """Get phase description."""
    phase_def = PHASES.get(phase_name)
    return phase_def.description if phase_def else ""


def is_valid_phase(phase_name: str) -> bool:
    """Check if phase name is valid."""
    return phase_name in PHASES
