"""
Triage agent tools.

Tools available to the triage agent for routing calls to appropriate desks.
"""

import logging
from typing import Any, Dict, Optional

from voiceshared.tools import register_tool

logger = logging.getLogger(__name__)


@register_tool(
    description="Route call to fault desk for internet/equipment issues",
    parameters={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of customer's fault issue",
            },
            "caller_attrs": {
                "type": "object",
                "description": "Known caller attributes (phone, area code, etc.)",
                "properties": {
                    "phone_number": {"type": "string"},
                    "area_code_hint": {"type": "string"},
                    "customer_id": {"type": "string"},
                },
            },
        },
        "required": ["summary"],
    },
)
async def route_to_fault_desk(summary: str, caller_attrs: Optional[Dict[str, Any]] = None) -> str:
    """
    Route call to fault desk.

    Args:
        summary: Summary of customer's issue
        caller_attrs: Known caller attributes

    Returns:
        Confirmation message
    """
    logger.info(f"Routing to fault desk: {summary}")

    # This will trigger handoff in the WebSocket handler
    # Return a natural response for the agent
    return "故障窓口におつなぎいたします。そのままお待ちください。"


@register_tool(
    description="Route call to billing desk for payment/invoice issues",
    parameters={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of customer's billing issue",
            },
            "caller_attrs": {
                "type": "object",
                "description": "Known caller attributes",
            },
        },
        "required": ["summary"],
    },
)
async def route_to_billing_desk(summary: str, caller_attrs: Optional[Dict[str, Any]] = None) -> str:
    """Route call to billing desk (future implementation)."""
    logger.info(f"Routing to billing desk: {summary}")
    return "料金窓口におつなぎいたします。そのままお待ちください。"


@register_tool(
    description="Route call to general desk for other inquiries",
    parameters={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of customer's inquiry",
            },
            "caller_attrs": {
                "type": "object",
                "description": "Known caller attributes",
            },
        },
        "required": ["summary"],
    },
)
async def route_to_general_desk(summary: str, caller_attrs: Optional[Dict[str, Any]] = None) -> str:
    """Route call to general desk (future implementation)."""
    logger.info(f"Routing to general desk: {summary}")
    return "総合窓口におつなぎいたします。そのままお待ちください。"


@register_tool(
    description="End the call normally",
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Reason for ending call",
            }
        },
    },
)
async def end_call(reason: Optional[str] = None) -> str:
    """End the call."""
    logger.info(f"Ending call: {reason}")
    return "お電話ありがとうございました。失礼いたします。"


@register_tool(
    description="Escalate to human operator when agent cannot handle",
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Reason for escalation",
            }
        },
        "required": ["reason"],
    },
)
async def escalate_to_human(reason: str) -> str:
    """Escalate to human operator."""
    logger.warning(f"Escalating to human: {reason}")
    return "担当者におつなぎいたします。少々お待ちください。"


def register_triage_tools():
    """
    Register all triage tools.

    This function is called at startup to ensure all tools are registered.
    The tools are already registered via decorators, but this provides
    an explicit registration point.
    """
    logger.info("Triage tools registered")
    # Tools are automatically registered via @register_tool decorator
    # This function serves as documentation and explicit initialization point
