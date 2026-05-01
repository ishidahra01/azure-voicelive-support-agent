"""
Summarizer skill.

Summarizes conversation history for context management using OOB Foundry.
"""

from typing import Any, Dict

from voiceshared.oob import get_oob_client
from .base import BaseSkill, SkillResult


class SummarizerSkill(BaseSkill):
    """Skill for conversation summarization."""

    def __init__(self, call_id: str):
        """Initialize summarizer skill."""
        super().__init__(call_id, "summarizer")
        self.oob_client = get_oob_client()

    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        Summarize conversation.

        Args:
            params: Dict with utterances, max_length, style

        Returns:
            SkillResult with summary
        """
        utterances = params.get("utterances", [])
        max_length = params.get("max_length", 500)
        style = params.get("style", "concise")

        if not utterances:
            return SkillResult(
                structured={"summary": ""},
                conversational="",
                success=False,
                error="no utterances to summarize",
            )

        self.logger.info(f"Summarizing {len(utterances)} utterances")

        # Combine utterances into text
        text = "\n".join([
            f"{u.get('role', 'unknown')}: {u.get('text', '')}"
            for u in utterances
        ])

        # For demo, create a simple summary without calling actual OOB
        # In production, would call:
        # summary = await self.oob_client.summarize(text, max_length, style)

        # Mock summarization
        summary = f"会話の要約（{len(utterances)}発話）: " + text[:min(len(text), max_length)]

        # Extract key points (mock)
        key_points = []
        for u in utterances[:3]:  # First 3 utterances
            if u.get("text"):
                key_points.append(u.get("text")[:50] + "...")

        # Simple sentiment analysis (mock)
        sentiment = "neutral"
        if "ありがとう" in text or "助かり" in text:
            sentiment = "positive"
        elif "困って" in text or "怒" in text:
            sentiment = "negative"

        # Determine urgency
        urgency = "medium"
        if "緊急" in text or "すぐ" in text or "至急" in text:
            urgency = "high"

        structured = {
            "summary": summary,
            "key_points": key_points,
            "sentiment": sentiment,
            "urgency": urgency,
        }

        # Conversational output not used (internal skill)
        return SkillResult(
            structured=structured,
            conversational="",
            success=True,
        )
