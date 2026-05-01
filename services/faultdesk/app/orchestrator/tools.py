"""
Orchestrator tools.

Tools available to the Voice Live orchestrator for managing conversation flow.
"""

import logging
from typing import Optional

from voiceshared.tools import register_tool
from app.skills import (
    IdentitySkill,
    InterviewSkill,
    LineTestSkill,
    VisitScheduleSkill,
    VisitConfirmSkill,
    HistorySkill,
)

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
    """Verify customer identity (calls IdentitySkill)."""
    logger.info(f"Verifying identity: customer_id={customer_id}")

    call_id = get_current_call_id()
    skill = IdentitySkill(call_id)

    result = await skill.execute({
        "customer_id": customer_id,
        "name": name,
        "address": address,
    })

    # Update slot store with structured result
    if result.success:
        slot_store = get_current_slot_store()
        if slot_store:
            for key, value in result.structured.items():
                slot_store.set("identity", key, value)

    # Log to call log
    call_log = get_current_call_log()
    if call_log:
        call_log.add_tool_call("verify_identity", {"customer_id": customer_id, "name": name}, result.structured)

    return result.conversational


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
    """Interview customer about fault (calls InterviewSkill)."""
    logger.info(f"Interviewing fault: symptom={symptom}")

    call_id = get_current_call_id()
    skill = InterviewSkill(call_id)

    result = await skill.execute({
        "symptom": symptom,
        "started_at": started_at,
    })

    # Update slot store
    if result.success:
        slot_store = get_current_slot_store()
        if slot_store:
            for key, value in result.structured.items():
                slot_store.set("interview", key, value)

    # Log to call log
    call_log = get_current_call_log()
    if call_log:
        call_log.add_tool_call("interview_fault", {"symptom": symptom, "started_at": started_at}, result.structured)

    return result.conversational


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

    call_id = get_current_call_id()
    skill = LineTestSkill(call_id)

    result = await skill.execute({
        "customer_id": customer_id,
    })

    # Update slot store
    if result.success:
        slot_store = get_current_slot_store()
        if slot_store:
            for key, value in result.structured.items():
                slot_store.set("interview", key, value)

    # Log to call log
    call_log = get_current_call_log()
    if call_log:
        call_log.add_tool_call("run_line_test", {"customer_id": customer_id}, result.structured)

    return result.conversational


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
    """Propose visit slots (calls VisitScheduleSkill)."""
    logger.info(f"Proposing visit slots: area={area_code}, urgency={urgency}")

    call_id = get_current_call_id()
    skill = VisitScheduleSkill(call_id)

    result = await skill.execute({
        "customer_id": customer_id,
        "area_code": area_code,
        "urgency": urgency,
    })

    # Update slot store
    if result.success:
        slot_store = get_current_slot_store()
        if slot_store:
            for key, value in result.structured.items():
                slot_store.set("visit", key, value)

    # Log to call log
    call_log = get_current_call_log()
    if call_log:
        call_log.add_tool_call("propose_visit_slots", {"area_code": area_code, "urgency": urgency}, result.structured)

    return result.conversational


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
    """Confirm visit (calls VisitConfirmSkill)."""
    logger.info(f"Confirming visit: slot_id={slot_id}")

    call_id = get_current_call_id()
    skill = VisitConfirmSkill(call_id)

    result = await skill.execute({
        "customer_id": customer_id,
        "slot_id": slot_id,
        "customer_confirmation": confirmation,
    })

    # Update slot store
    if result.success:
        slot_store = get_current_slot_store()
        if slot_store:
            for key, value in result.structured.items():
                slot_store.set("visit", key, value)

    # Log to call log
    call_log = get_current_call_log()
    if call_log:
        call_log.add_tool_call("confirm_visit", {"slot_id": slot_id, "customer_id": customer_id}, result.structured)

    return result.conversational


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
    """Record history (calls HistorySkill)."""
    logger.info(f"Recording history: {summary}")

    call_id = get_current_call_id()
    skill = HistorySkill(call_id)

    result = await skill.execute({
        "customer_id": customer_id,
        "summary": summary,
    })

    # Update slot store
    if result.success:
        slot_store = get_current_slot_store()
        if slot_store:
            slot_store.set("closing", "history_recorded", True)

    # Log to call log
    call_log = get_current_call_log()
    if call_log:
        call_log.add_tool_call("record_history", {"summary": summary, "customer_id": customer_id}, result.structured)

    return result.conversational


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
