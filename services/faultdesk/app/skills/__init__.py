"""
Skills for business logic execution.

Skills are independent agents that handle specific tasks like identity verification,
fault diagnosis, visit scheduling, etc.
"""

from .base import BaseSkill, SkillResult
from .identity import IdentitySkill
from .interview import InterviewSkill
from .line_test import LineTestSkill
from .visit_schedule import VisitScheduleSkill
from .visit_confirm import VisitConfirmSkill
from .history import HistorySkill
from .summarizer import SummarizerSkill

__all__ = [
    "BaseSkill",
    "SkillResult",
    "IdentitySkill",
    "InterviewSkill",
    "LineTestSkill",
    "VisitScheduleSkill",
    "VisitConfirmSkill",
    "HistorySkill",
    "SummarizerSkill",
]
