"""
Fault interview skill.

Gathers detailed information about fault symptoms through guided questioning.
"""

from typing import Any, Dict, Optional

from app.adapters import get_cultas_client, get_ai_search_client
from .base import BaseSkill, SkillResult


class InterviewSkill(BaseSkill):
    """Skill for fault symptom interview."""

    def __init__(self, call_id: str):
        """Initialize interview skill."""
        super().__init__(call_id, "interview")
        self.cultas = get_cultas_client()
        self.ai_search = get_ai_search_client()

    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        Conduct fault interview.

        Args:
            params: Dict with symptom, started_at, context

        Returns:
            SkillResult with interview data
        """
        symptom = params.get("symptom")
        started_at = params.get("started_at")
        context = params.get("context", {})

        self.logger.info(f"Interviewing fault: symptom={symptom}")

        # Add to thread context
        self._add_to_thread("user", self._format_params_message(params))

        # Get AI diagnosis
        diagnosis = await self.cultas.diagnose_symptom(symptom or "", context)

        # Search knowledge base for related info
        kb_results = await self.ai_search.search_interview_kb(symptom or "")

        # Build structured result
        structured = {
            "fault_symptom": symptom,
            "fault_started_at": started_at,
            "suspected_cause": diagnosis.get("suspected_cause"),
            "urgency": diagnosis.get("urgency", "medium"),
            "diagnosis_complete": bool(symptom and started_at),
            "recommended_questions": diagnosis.get("recommended_questions", []),
        }

        # Generate conversational response
        if symptom and started_at:
            conversational = f"承知いたしました。{symptom}が{started_at}から発生しているのですね。"

            # Add follow-up questions
            questions = diagnosis.get("recommended_questions", [])
            if questions:
                conversational += f"{questions[0]}"
        else:
            conversational = "故障の症状について詳しくお聞かせいただけますでしょうか。"

        return SkillResult(
            structured=structured,
            conversational=conversational,
            success=True,
        )
