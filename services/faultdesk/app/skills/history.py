"""
History recording skill.

Records interaction history to 113SF system.
"""

from typing import Any, Dict

from app.adapters import get_sf113_client, get_cultas_client
from .base import BaseSkill, SkillResult


class HistorySkill(BaseSkill):
    """Skill for recording history."""

    def __init__(self, call_id: str):
        """Initialize history skill."""
        super().__init__(call_id, "history")
        self.sf113 = get_sf113_client()
        self.cultas = get_cultas_client()

    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        Record interaction history.

        Args:
            params: Dict with customer_id, summary, resolution, tags

        Returns:
            SkillResult with history record
        """
        customer_id = params.get("customer_id")
        summary = params.get("summary", "")
        resolution = params.get("resolution", "")
        tags = params.get("tags", [])

        if not customer_id:
            return SkillResult(
                structured={"success": False},
                conversational="",
                success=False,
                error="customer_id required",
            )

        self.logger.info(f"Recording history for customer {customer_id}")

        # Categorize issue
        categorization = await self.cultas.categorize_issue(summary)

        # Build history data
        history_data = {
            "summary": summary,
            "resolution": resolution,
            "tags": tags + categorization.get("tags", []),
            "category": categorization.get("category"),
        }

        # Post to 113SF
        result = await self.sf113.post_history(customer_id, history_data)

        if not result.get("success"):
            return SkillResult(
                structured={"success": False},
                conversational="履歴の記録に失敗しました。",
                success=False,
                error="history post failed",
            )

        # Build structured result
        structured = {
            "history_id": result.get("history_id"),
            "recorded_at": result.get("recorded_at"),
            "success": True,
        }

        conversational = "本日の内容を記録いたしました。"

        return SkillResult(
            structured=structured,
            conversational=conversational,
            success=True,
        )
