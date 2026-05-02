"""
Microsoft Agent Framework file-based Agent Skills for faultdesk.

Skill instructions are maintained as ``catalog/*/SKILL.md`` files and attached
to a single MAF ``Agent`` through ``SkillsProvider``. Backend actions are Python
tools so they can update per-call SlotStore and CallLog in-process.
"""

from .agent import get_faultdesk_agent, get_faultdesk_session, run_faultdesk_agent
from .tools import SKILLS_CATALOG_PATH, get_faultdesk_tools

__all__ = [
    "get_faultdesk_agent",
    "get_faultdesk_session",
    "get_faultdesk_tools",
    "SKILLS_CATALOG_PATH",
    "run_faultdesk_agent",
]
