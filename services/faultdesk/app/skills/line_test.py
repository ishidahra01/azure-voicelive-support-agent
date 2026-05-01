"""
Line test skill.

Executes remote line tests and interprets results.
"""

from typing import Any, Dict

from app.adapters import get_sf113_client, get_cultas_client
from .base import BaseSkill, SkillResult


class LineTestSkill(BaseSkill):
    """Skill for remote line testing."""

    def __init__(self, call_id: str):
        """Initialize line test skill."""
        super().__init__(call_id, "line_test")
        self.sf113 = get_sf113_client()
        self.cultas = get_cultas_client()

    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        Execute line test.

        Args:
            params: Dict with customer_id, test_type, context

        Returns:
            SkillResult with test results
        """
        customer_id = params.get("customer_id")
        test_type = params.get("test_type", "basic")
        context = params.get("context", {})

        if not customer_id:
            return SkillResult(
                structured={"test_executed": False},
                conversational="お客様番号が必要です。",
                success=False,
                error="customer_id required",
            )

        self.logger.info(f"Running line test for customer {customer_id}")

        # Inform customer
        conversational = "回線試験を実施いたします。30秒ほどお待ちください。"

        # Execute test
        test_results = await self.sf113.run_line_test(customer_id, test_type)

        # Interpret results
        interpretation = await self.cultas.interpret_test(test_results)

        # Build structured result
        structured = {
            "test_executed": True,
            "test_id": test_results.get("test_id"),
            "results": test_results.get("results"),
            "interpretation": interpretation.get("interpretation"),
            "recommended_action": interpretation.get("recommended_action"),
            "line_status": test_results.get("line_status"),
        }

        # Add results to conversational text
        conversational += " " + interpretation.get("explanation", "")

        return SkillResult(
            structured=structured,
            conversational=conversational,
            success=True,
        )
