"""
Backend tools used by file-based Agent Skills.

The skill instructions live in ``catalog/*/SKILL.md`` and are discovered by
``SkillsProvider``. These functions stay in Python because they need in-process
access to SlotStore, CallLog, and service adapters through
``function_invocation_kwargs``.
"""

from __future__ import annotations

import json
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework import tool

from app.adapters import get_ai_search_client, get_cultas_client, get_sf113_client


SKILLS_CATALOG_PATH = Path(__file__).parent / "catalog"
_runtime_context: ContextVar[Dict[str, Any]] = ContextVar("faultdesk_skill_runtime_context", default={})


def set_faultdesk_tool_context(**kwargs: Any) -> Token[Dict[str, Any]]:
    """Set task-local runtime context for backend tools during one agent run."""
    return _runtime_context.set({key: value for key, value in kwargs.items() if value is not None})


def reset_faultdesk_tool_context(token: Token[Dict[str, Any]]) -> None:
    """Reset task-local runtime context after an agent run."""
    _runtime_context.reset(token)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _slot_store(kwargs: Dict[str, Any]) -> Any:
    return kwargs.get("slot_store") or _runtime_context.get().get("slot_store")


def _call_log(kwargs: Dict[str, Any]) -> Any:
    return kwargs.get("call_log") or _runtime_context.get().get("call_log")


def _set_slot(kwargs: Dict[str, Any], phase: str, name: str, value: Any) -> None:
    slot_store = _slot_store(kwargs)
    if slot_store is not None and value is not None:
        slot_store.set(phase, name, value)


def _log_tool(kwargs: Dict[str, Any], tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> None:
    call_log = _call_log(kwargs)
    if call_log is not None:
        call_log.add_tool_call(tool_name, arguments, result)


@tool
def get_current_context(**kwargs: Any) -> str:
    """Return current call phase and filled slots as JSON."""
    phase_state = kwargs.get("phase_state")
    slot_store = kwargs.get("slot_store")
    context = _runtime_context.get()
    phase_state = phase_state or context.get("phase_state")
    slot_store = slot_store or context.get("slot_store")
    data = {
        "call_id": kwargs.get("call_id") or context.get("call_id"),
        "current_phase": getattr(phase_state, "current", None),
        "filled_slots": slot_store.get_all_filled_slots() if slot_store else {},
    }
    return _json(data)


@tool
async def verify_identity(
    customer_id: Optional[str] = None,
    name: Optional[str] = None,
    address: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Verify customer identity against SF113 and update identity slots."""
    sf113 = get_sf113_client()
    structured: Dict[str, Any] = {"verified": False}

    if customer_id:
        customer = await sf113.get_customer(customer_id)
        if customer:
            structured.update(
                {
                    "verified": True,
                    "customer_id": customer["customer_id"],
                    "customer_record": customer,
                    "verification_method": "customer_id",
                }
            )
        else:
            structured["reason"] = "customer_id_not_found"
    elif name:
        matches = await sf113.fuzzy_match_name(name)
        if matches and address:
            for match in matches:
                address_result = await sf113.verify_address(address, match)
                if address_result.get("match"):
                    structured.update(
                        {
                            "verified": True,
                            "customer_id": match["customer_id"],
                            "customer_record": match,
                            "verification_method": "name_address",
                        }
                    )
                    break
            else:
                structured.update({"reason": "address_mismatch", "candidates": matches})
        elif matches:
            structured.update({"reason": "need_address", "candidates": matches})
        else:
            structured["reason"] = "name_not_found"
    else:
        structured["reason"] = "need_customer_id_or_name"

    if structured.get("verified"):
        customer = structured["customer_record"]
        _set_slot(kwargs, "identity", "customer_id", customer.get("customer_id"))
        _set_slot(kwargs, "identity", "name_match", True)
        _set_slot(kwargs, "identity", "address_match", bool(address) or bool(customer_id))
        _set_slot(kwargs, "identity", "contact_phone", customer.get("phone"))
        _set_slot(kwargs, "identity", "verification_status", "verified")
    else:
        _set_slot(kwargs, "identity", "verification_status", structured.get("reason", "unverified"))

    _log_tool(
        kwargs,
        "verify_identity",
        {"customer_id": customer_id, "name": name, "address": address},
        structured,
    )
    return _json(structured)


@tool
async def diagnose_fault(symptom: str, started_at: Optional[str] = None, **kwargs: Any) -> str:
    """Diagnose a fault symptom with CULTAS and update interview slots."""
    cultas = get_cultas_client()
    diagnosis = await cultas.diagnose_symptom(symptom, {})
    structured = {
        "fault_symptom": symptom,
        "fault_started_at": started_at,
        "suspected_cause": diagnosis.get("suspected_cause"),
        "urgency": diagnosis.get("urgency", "medium"),
        "diagnosis_complete": bool(symptom and started_at),
        "recommended_questions": diagnosis.get("recommended_questions", []),
        "recommended_action": diagnosis.get("recommended_action"),
    }
    _set_slot(kwargs, "interview", "fault_symptom", symptom)
    _set_slot(kwargs, "interview", "fault_started_at", started_at)
    _set_slot(kwargs, "interview", "suspected_cause", structured["suspected_cause"])
    _set_slot(kwargs, "interview", "diagnosis_complete", structured["diagnosis_complete"])
    _log_tool(kwargs, "diagnose_fault", {"symptom": symptom, "started_at": started_at}, structured)
    return _json(structured)


@tool
async def search_interview_knowledge(query: str, top_k: int = 3, **kwargs: Any) -> str:
    """Search interview knowledge base articles."""
    ai_search = get_ai_search_client()
    results = await ai_search.search_interview_kb(query, top_k=top_k)
    structured = {"query": query, "results": results}
    _log_tool(kwargs, "search_interview_knowledge", {"query": query, "top_k": top_k}, structured)
    return _json(structured)


@tool
async def run_line_test(customer_id: str, test_type: str = "basic", **kwargs: Any) -> str:
    """Run SF113 line test, interpret it with CULTAS, and update interview slots."""
    sf113 = get_sf113_client()
    cultas = get_cultas_client()
    test_results = await sf113.run_line_test(customer_id, test_type)
    interpretation = await cultas.interpret_test(test_results)
    structured = {
        "test_executed": True,
        "test_results": test_results,
        "interpretation": interpretation,
        "line_status": test_results.get("line_status"),
        "recommended_action": interpretation.get("recommended_action"),
    }
    _set_slot(kwargs, "interview", "line_test_result", structured)
    _set_slot(kwargs, "interview", "suspected_cause", interpretation.get("interpretation"))
    _log_tool(kwargs, "run_line_test", {"customer_id": customer_id, "test_type": test_type}, structured)
    return _json(structured)


@tool
async def propose_visit_slots(
    area_code: str = "03",
    urgency: str = "medium",
    customer_id: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Fetch and prioritize technician visit slots, updating visit slots."""
    sf113 = get_sf113_client()
    cultas = get_cultas_client()
    slots = await sf113.get_visit_slots(area_code, "fault_repair")
    candidates = await cultas.filter_slots(slots, urgency)
    structured = {
        "customer_id": customer_id,
        "available": bool(candidates),
        "candidates": candidates,
        "recommended_slot_id": candidates[0]["slot_id"] if candidates else None,
    }
    _set_slot(kwargs, "visit", "visit_required", True)
    _set_slot(kwargs, "visit", "visit_candidates", candidates)
    _log_tool(kwargs, "propose_visit_slots", {"area_code": area_code, "urgency": urgency}, structured)
    return _json(structured)


@tool
async def confirm_visit(customer_id: str, slot_id: str, notes: str = "", **kwargs: Any) -> str:
    """Book a selected technician visit slot and update visit slots."""
    sf113 = get_sf113_client()
    dispatch_order = await sf113.book_visit(customer_id, slot_id, notes)
    structured = {"confirmed": bool(dispatch_order), "dispatch_order": dispatch_order}
    if dispatch_order:
        _set_slot(kwargs, "visit", "visit_confirmed", dispatch_order)
        _set_slot(kwargs, "visit", "dispatch_id", dispatch_order.get("dispatch_id"))
    _log_tool(kwargs, "confirm_visit", {"customer_id": customer_id, "slot_id": slot_id}, structured)
    return _json(structured)


@tool
async def summarize_call(max_length: int = 500, **kwargs: Any) -> str:
    """Summarize current call log utterances."""
    call_log = _call_log(kwargs)
    utterances: List[Dict[str, Any]] = getattr(call_log, "utterances", []) if call_log else []
    text = "\n".join(f"{u.get('role', 'unknown')}: {u.get('text', '')}" for u in utterances)
    summary = text[:max_length] if text else ""
    structured = {
        "summary": summary,
        "utterance_count": len(utterances),
        "urgency": "high" if any(word in text for word in ("緊急", "至急", "すぐ")) else "medium",
        "sentiment": "negative" if any(word in text for word in ("困", "怒", "不満")) else "neutral",
    }
    _log_tool(kwargs, "summarize_call", {"max_length": max_length}, structured)
    return _json(structured)


@tool
async def record_history(
    summary: str,
    customer_id: Optional[str] = None,
    resolution: str = "",
    **kwargs: Any,
) -> str:
    """Categorize and save a call summary to SF113."""
    sf113 = get_sf113_client()
    cultas = get_cultas_client()
    categorization = await cultas.categorize_issue(summary)
    history_data = {
        "summary": summary,
        "resolution": resolution,
        "tags": categorization.get("tags", []),
        "category": categorization.get("category"),
    }
    if not customer_id:
        slot_store = _slot_store(kwargs)
        customer_id = slot_store.get("identity", "customer_id") if slot_store else None
    if not customer_id:
        structured = {"success": False, "reason": "customer_id_required"}
    else:
        result = await sf113.post_history(customer_id, history_data)
        structured = {"success": bool(result.get("success")), "history": result}
        if result.get("success"):
            _set_slot(kwargs, "closing", "history_recorded", True)
    _log_tool(kwargs, "record_history", {"summary": summary, "customer_id": customer_id}, structured)
    return _json(structured)


def get_faultdesk_tools() -> List[Any]:
    """Return tools available to file-based faultdesk skills."""
    return [
        get_current_context,
        verify_identity,
        diagnose_fault,
        search_interview_knowledge,
        run_line_test,
        propose_visit_slots,
        confirm_visit,
        summarize_call,
        record_history,
    ]