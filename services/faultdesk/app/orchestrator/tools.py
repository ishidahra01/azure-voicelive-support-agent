"""
Orchestrator tools.

Tools available to the Voice Live orchestrator for managing conversation flow.
"""

import logging
from typing import Any, Dict, Optional

from voiceshared.tools import register_tool

logger = logging.getLogger(__name__)


@register_tool(
    description="Jump to a different conversation phase",
    parameters={
        "type": "object",
        "properties": {
            "target_phase": {
                "type": "string",
                "description": "Target phase name",
                "enum": ["intake", "identity", "interview", "visit", "closing"],
            },
            "reason": {
                "type": "string",
                "description": "Reason for jumping",
            },
        },
        "required": ["target_phase"],
    },
)
async def jump_to_phase(target_phase: str, reason: Optional[str] = None) -> str:
    """Jump to a different phase."""
    logger.info(f"Jump to phase: {target_phase}, reason: {reason}")
    return f"{target_phase}フェーズに移ります。"


@register_tool(
    description="Verify customer identity",
    parameters={
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "8桁のお客様番号"},
            "name": {"type": "string", "description": "お客様のお名前"},
            "address": {"type": "string", "description": "ご住所"},
        },
    },
)
async def verify_identity(
    customer_id: Optional[str] = None,
    name: Optional[str] = None,
    address: Optional[str] = None,
) -> str:
    """Verify customer identity (calls IdentitySkill)."""
    logger.info(f"Verifying identity: customer_id={customer_id}")
    # In real impl: Call IdentitySkill
    return "ご本人確認できました。"


@register_tool(
    description="Interview customer about fault details",
    parameters={
        "type": "object",
        "properties": {
            "symptom": {"type": "string", "description": "故障症状"},
            "started_at": {"type": "string", "description": "発生時期"},
        },
    },
)
async def interview_fault(
    symptom: Optional[str] = None, started_at: Optional[str] = None
) -> str:
    """Interview customer about fault (calls InterviewSkill)."""
    logger.info(f"Interviewing fault: symptom={symptom}")
    # In real impl: Call InterviewSkill
    return "故障状況を確認しました。"


@register_tool(
    description="Run remote line test",
    parameters={
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "お客様番号"},
        },
        "required": ["customer_id"],
    },
)
async def run_line_test(customer_id: str) -> str:
    """Run line test (calls LineTestSkill)."""
    logger.info(f"Running line test for customer: {customer_id}")
    # In real impl: Call LineTestSkill
    return "回線試験を実施しました。回線に問題が検出されました。"


@register_tool(
    description="Propose visit time slots",
    parameters={
        "type": "object",
        "properties": {
            "area_code": {"type": "string", "description": "地域コード"},
            "urgency": {"type": "string", "description": "緊急度"},
        },
    },
)
async def propose_visit_slots(
    area_code: Optional[str] = None, urgency: str = "medium"
) -> str:
    """Propose visit slots (calls VisitScheduleSkill)."""
    logger.info(f"Proposing visit slots: area={area_code}, urgency={urgency}")
    # In real impl: Call VisitScheduleSkill
    return "訪問日程の候補をご提案します。明日の午前9時から12時、または午後2時から5時が空いております。"


@register_tool(
    description="Confirm visit appointment",
    parameters={
        "type": "object",
        "properties": {
            "slot_id": {"type": "string", "description": "選択されたスロットID"},
            "confirmation": {"type": "string", "description": "お客様の確認"},
        },
        "required": ["slot_id"],
    },
)
async def confirm_visit(slot_id: str, confirmation: Optional[str] = None) -> str:
    """Confirm visit (calls VisitConfirmSkill)."""
    logger.info(f"Confirming visit: slot_id={slot_id}")
    # In real impl: Call VisitConfirmSkill
    return "訪問修理の手配が完了しました。手配番号はDS-123456です。"


@register_tool(
    description="Record interaction history",
    parameters={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "対応内容のサマリ"},
        },
        "required": ["summary"],
    },
)
async def record_history(summary: str) -> str:
    """Record history (calls HistorySkill)."""
    logger.info(f"Recording history: {summary}")
    # In real impl: Call HistorySkill
    return "対応履歴を記録しました。"


@register_tool(
    description="Handoff to human operator",
    parameters={
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "エスカレーション理由"},
        },
        "required": ["reason"],
    },
)
async def handoff_to_operator(reason: str) -> str:
    """Handoff to human operator."""
    logger.warning(f"Escalating to operator: {reason}")
    return "担当者におつなぎいたします。"


def register_orchestrator_tools():
    """Register all orchestrator tools."""
    logger.info("Orchestrator tools registered")
    # Tools are automatically registered via @register_tool decorator
