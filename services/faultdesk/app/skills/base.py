"""
Base skill class.

Provides common functionality for all skills including context management
and structured output formatting.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.context import get_thread_store

logger = logging.getLogger(__name__)


@dataclass
class SkillResult:
    """
    Result from skill execution.

    Contains both structured data for slot updates and conversational text
    for voice output.
    """

    structured: Dict[str, Any]
    conversational: str
    success: bool = True
    error: Optional[str] = None


class BaseSkill(ABC):
    """Base class for all skills."""

    def __init__(self, call_id: str, skill_name: str):
        """
        Initialize skill.

        Args:
            call_id: Call identifier
            skill_name: Name of this skill
        """
        self.call_id = call_id
        self.skill_name = skill_name
        self.thread_store = get_thread_store()
        self.thread = self.thread_store.get_or_create(call_id, skill_name)
        self.logger = logging.getLogger(f"{__name__}.{skill_name}")

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        Execute skill logic.

        Args:
            params: Input parameters

        Returns:
            SkillResult with structured and conversational outputs
        """
        pass

    def _add_to_thread(self, role: str, content: str):
        """Add message to skill's thread."""
        self.thread.add_message(role, content)

    def _format_params_message(self, params: Dict[str, Any]) -> str:
        """Format parameters as message for thread context."""
        parts = []
        for key, value in params.items():
            if value is not None:
                parts.append(f"{key}: {value}")
        return "Parameters: " + ", ".join(parts) if parts else "No parameters provided"
