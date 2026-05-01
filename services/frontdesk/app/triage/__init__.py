"""Triage package initialization."""

from .instructions import get_triage_instructions
from .tools import register_triage_tools

__all__ = ["get_triage_instructions", "register_triage_tools"]
