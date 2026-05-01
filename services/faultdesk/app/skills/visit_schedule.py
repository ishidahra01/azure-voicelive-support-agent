"""
Visit schedule skill.

Retrieves and presents available visit time slots.
"""

from typing import Any, Dict, Optional

from app.adapters import get_sf113_client, get_cultas_client
from .base import BaseSkill, SkillResult


class VisitScheduleSkill(BaseSkill):
    """Skill for visit scheduling."""

    def __init__(self, call_id: str):
        """Initialize visit schedule skill."""
        super().__init__(call_id, "visit_schedule")
        self.sf113 = get_sf113_client()
        self.cultas = get_cultas_client()

    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        Get available visit slots.

        Args:
            params: Dict with customer_id, area_code, urgency, preferred_dates

        Returns:
            SkillResult with available slots
        """
        customer_id = params.get("customer_id")
        area_code = params.get("area_code")
        urgency = params.get("urgency", "medium")
        preferred_dates = params.get("preferred_dates", [])

        self.logger.info(f"Getting visit slots for area {area_code}, urgency {urgency}")

        # Get available slots
        slots = await self.sf113.get_visit_slots(area_code or "03", "fault_repair")

        # Filter by urgency
        filtered_slots = await self.cultas.filter_slots(slots, urgency)

        if not filtered_slots:
            return SkillResult(
                structured={"candidates": [], "available": False},
                conversational="申し訳ございません。現在空きがございません。別の日程でご案内できます。",
                success=False,
            )

        # Build structured result
        structured = {
            "candidates": filtered_slots,
            "recommended_slot_id": filtered_slots[0]["slot_id"] if filtered_slots else None,
            "earliest_available": filtered_slots[0]["date"] if filtered_slots else None,
        }

        # Generate conversational response
        conversational = "訪問日程をご提案させていただきます。"

        # Present top 2-3 slots
        for i, slot in enumerate(filtered_slots[:3]):
            date = slot["date"]
            time_range = slot["time_range"]
            if i == 0:
                conversational += f"{date}の{time_range}"
            elif i == len(filtered_slots[:3]) - 1:
                conversational += f"、または{date}の{time_range}"
            else:
                conversational += f"、{date}の{time_range}"

        conversational += "が空いております。いずれかご都合よろしい時間帯はございますでしょうか。"

        return SkillResult(
            structured=structured,
            conversational=conversational,
            success=True,
        )
