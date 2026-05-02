"""
Orchestrator tools.

Tools available to the Voice Live orchestrator for managing conversation flow.
"""

import logging
from typing import Optional

from voiceshared.tools import register_tool
from app.skills import run_faultdesk_agent

logger = logging.getLogger(__name__)

# Session context for tools (set by main.py)
_current_context: dict = {}


def set_tool_context(call_id: str, slot_store, phase_state, call_log):
    """Set context for tool execution."""
    _current_context["call_id"] = call_id
    _current_context["slot_store"] = slot_store
    _current_context["phase_state"] = phase_state
    _current_context["call_log"] = call_log


def get_current_call_id() -> str:
    """Get current call ID from context."""
    return _current_context.get("call_id", "unknown")


def get_current_slot_store():
    """Get current slot store from context."""
    return _current_context.get("slot_store")


def get_current_phase_state():
    """Get current phase state from context."""
    return _current_context.get("phase_state")


def get_current_call_log():
    """Get current call log from context."""
    return _current_context.get("call_log")


async def _run_faultdesk_skill_task(task: str) -> str:
    """Run the MAF Agent with file-based Agent Skills for the active call."""
    return await run_faultdesk_agent(
        call_id=get_current_call_id(),
        task=task,
        slot_store=get_current_slot_store(),
        phase_state=get_current_phase_state(),
        call_log=get_current_call_log(),
    )


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

    # Update phase state
    phase_state = get_current_phase_state()
    if phase_state:
        phase_state.transition_to(target_phase, trigger=f"jump:{reason or 'manual'}")

    # Log to call log
    call_log = get_current_call_log()
    if call_log:
        call_log.add_tool_call("jump_to_phase", {"target_phase": target_phase, "reason": reason})

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
    """Verify customer identity using the MAF Agent Skills provider."""
    logger.info(f"Verifying identity: customer_id={customer_id}")

    return await _run_faultdesk_skill_task(
        "本人確認フェーズです。identity-verification skill を load_skill で読み、手順に従い、"
        "必要なら verify_identity backend tool を実行してください。"
        f" 入力: customer_id={customer_id}, name={name}, address={address}. "
        "tool結果を踏まえ、お客様への次の一言だけを返してください。"
    )


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
async def interview_fault(symptom: Optional[str] = None, started_at: Optional[str] = None) -> str:
    """Interview customer about fault using the MAF Agent Skills provider."""
    logger.info(f"Interviewing fault: symptom={symptom}")

    return await _run_faultdesk_skill_task(
        "故障ヒアリングフェーズです。fault-interview skill を load_skill で読み、手順に従い、"
        "必要なら diagnose_fault / search_interview_knowledge backend tool を実行してください。"
        f" 入力: symptom={symptom}, started_at={started_at}. "
        "未確定の重要情報があれば質問は一つだけにしてください。"
    )


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
    """Run line test using the MAF Agent Skills provider."""
    logger.info(f"Running line test for customer: {customer_id}")

    return await _run_faultdesk_skill_task(
        "line-test skill を load_skill で読み、手順に従い、run_line_test backend tool を実行してください。"
        f" 入力: customer_id={customer_id}. "
        "試験結果と推奨アクションを、お客様に分かる短い日本語で説明してください。"
    )


@register_tool(
    description="Propose visit time slots",
    parameters={
        "type": "object",
        "properties": {
            "area_code": {"type": "string", "description": "地域コード"},
            "urgency": {"type": "string", "description": "緊急度"},
            "customer_id": {"type": "string", "description": "お客様番号"},
        },
    },
)
async def propose_visit_slots(
    area_code: Optional[str] = None,
    urgency: str = "medium",
    customer_id: Optional[str] = None,
) -> str:
    """Propose visit slots using the MAF Agent Skills provider."""
    logger.info(f"Proposing visit slots: area={area_code}, urgency={urgency}")

    return await _run_faultdesk_skill_task(
        "visit-scheduling skill を load_skill で読み、手順に従い、propose_visit_slots backend tool を実行してください。"
        f" 入力: customer_id={customer_id}, area_code={area_code}, urgency={urgency}. "
        "候補を最大3件まで、自然な日本語で提示してください。"
    )


@register_tool(
    description="Confirm visit appointment",
    parameters={
        "type": "object",
        "properties": {
            "slot_id": {"type": "string", "description": "選択されたスロットID"},
            "confirmation": {"type": "string", "description": "お客様の確認"},
            "customer_id": {"type": "string", "description": "お客様番号"},
        },
        "required": ["slot_id"],
    },
)
async def confirm_visit(
    slot_id: str,
    confirmation: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> str:
    """Confirm visit using the MAF Agent Skills provider."""
    logger.info(f"Confirming visit: slot_id={slot_id}")

    return await _run_faultdesk_skill_task(
        "visit-scheduling skill を load_skill で読み、手順に従い、confirm_visit backend tool を実行してください。"
        f" 入力: customer_id={customer_id}, slot_id={slot_id}, confirmation={confirmation}. "
        "確定した日時と手配番号を短く復唱してください。"
    )


@register_tool(
    description="Record interaction history",
    parameters={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "対応内容のサマリ"},
            "customer_id": {"type": "string", "description": "お客様番号"},
        },
        "required": ["summary"],
    },
)
async def record_history(summary: str, customer_id: Optional[str] = None) -> str:
    """Record history using the MAF Agent Skills provider."""
    logger.info(f"Recording history: {summary}")

    return await _run_faultdesk_skill_task(
        "history-recording skill を load_skill で読み、手順に従い、record_history backend tool を実行してください。"
        f" 入力: customer_id={customer_id}, summary={summary}. "
        "お客様には記録した旨だけを1文で伝えてください。"
    )


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

    # Log to call log
    call_log = get_current_call_log()
    if call_log:
        call_log.add_tool_call("handoff_to_operator", {"reason": reason})

    return "担当者におつなぎいたします。"


def register_orchestrator_tools():
    """Register all orchestrator tools."""
    logger.info("Orchestrator tools registered")
    # Tools are automatically registered via @register_tool decorator
