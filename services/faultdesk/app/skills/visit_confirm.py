"""
Visit confirmation skill.

Confirms visit appointment and creates dispatch order.
"""

from typing import Any, Dict

from app.adapters import get_sf113_client
from .base import BaseSkill, SkillResult


class VisitConfirmSkill(BaseSkill):
    """Skill for visit confirmation."""

    def __init__(self, call_id: str):
        """Initialize visit confirm skill."""
        super().__init__(call_id, "visit_confirm")
        self.sf113 = get_sf113_client()

    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        Confirm visit appointment.

        Args:
            params: Dict with customer_id, slot_id, customer_confirmation, notes

        Returns:
            SkillResult with dispatch order
        """
        customer_id = params.get("customer_id")
        slot_id = params.get("slot_id")
        confirmation = params.get("customer_confirmation", "")
        notes = params.get("notes", "")

        if not customer_id or not slot_id:
            return SkillResult(
                structured={"confirmed": False},
                conversational="お客様番号と日程が必要です。",
                success=False,
                error="missing required params",
            )

        self.logger.info(f"Confirming visit: customer={customer_id}, slot={slot_id}")

        # Book visit
        dispatch_order = await self.sf113.book_visit(customer_id, slot_id, notes)

        if not dispatch_order:
            return SkillResult(
                structured={"confirmed": False},
                conversational="申し訳ございません。予約ができませんでした。別の日程をご案内いたします。",
                success=False,
                error="booking failed",
            )

        # Build structured result
        structured = {
            "confirmed": True,
            "dispatch_id": dispatch_order["dispatch_id"],
            "visit_details": {
                "date": dispatch_order["date"],
                "time_range": dispatch_order["time_range"],
                "technician_name": dispatch_order.get("technician_name"),
                "contact_phone": dispatch_order.get("contact_phone"),
            },
            "confirmation_sent": True,
        }

        # Generate conversational response
        date = dispatch_order["date"]
        time_range = dispatch_order["time_range"]
        dispatch_id = dispatch_order["dispatch_id"]

        conversational = f"かしこまりました。{date}の{time_range}で手配いたしました。"
        conversational += f"手配番号は{dispatch_id}です。"
        conversational += "前日にSMSでご連絡させていただきます。"

        return SkillResult(
            structured=structured,
            conversational=conversational,
            success=True,
        )
