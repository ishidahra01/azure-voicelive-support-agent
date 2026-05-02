"""
Faultdesk Microsoft Agent Framework agent wired with file-based Agent Skills.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from agent_framework import Agent
from voiceshared.maf import create_chat_client

from app.config import config
from app.context import get_thread_store
from app.orchestrator.instructions import generate_instructions

from .tools import (
    SKILLS_CATALOG_PATH,
    get_faultdesk_tools,
    reset_faultdesk_tool_context,
    set_faultdesk_tool_context,
)

logger = logging.getLogger(__name__)


FAULTDESK_AGENT_SCOPE = "faultdesk-agent"


_agent: Optional[Agent] = None


def _load_skill_catalog_fallback_instructions() -> str:
    """Return file-based skill instructions for the non-Provider fallback path."""
    sections: list[str] = []
    for skill_file in sorted(SKILLS_CATALOG_PATH.glob("*/SKILL.md")):
        try:
            content = skill_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.warning("Failed to read skill file %s: %s", skill_file, exc)
            continue
        sections.append(f"## {skill_file.parent.name}\n{content}")

    if not sections:
        return ""

    return (
        "\n\n【利用可能なAgent Skillカタログ（fallback）】\n"
        "以下はfile-based Agent Skillsの内容です。SkillsProviderが無効な場合のみ、"
        "必要なskillの手順をこの内容から判断し、提供されたbackend toolsを直接呼び出してください。\n\n"
        + "\n\n".join(sections)
    )


def get_faultdesk_agent() -> Agent:
    """Return the process-wide faultdesk agent with file-based skills attached."""
    global _agent
    if _agent is None:
        context_providers = []
        skill_catalog_instructions = ""
        if config.maf_use_skills_provider:
            from agent_framework import SkillsProvider

            context_providers.append(SkillsProvider(skill_paths=SKILLS_CATALOG_PATH))
        else:
            skill_catalog_instructions = _load_skill_catalog_fallback_instructions()

        _agent = Agent(
            client=create_chat_client(
                azure_openai_endpoint=config.azure_openai_endpoint,
                azure_openai_api_key=config.azure_openai_api_key,
                azure_openai_api_version=config.azure_openai_api_version,
                azure_openai_model=config.azure_openai_model,
                foundry_project_endpoint=config.foundry_project_endpoint or None,
                foundry_model=config.foundry_model or None,
            ),
            name="FaultdeskSkillsAgent",
            instructions=(
                "あなたは故障受付窓口の担当者です。Phase+Slot状態を踏まえ、"
                "必要なAgent Skillをload_skillで読み、Skillの手順に従ってください。"
                "外部システム連携は提供されたbackend toolsで実行します。"
                "お客様への発話は短く丁寧な日本語で、1回に質問は1つだけにしてください。"
                f"{skill_catalog_instructions}"
            ),
            tools=get_faultdesk_tools(),
            context_providers=context_providers,
        )
        logger.info(
            "Created Faultdesk MAF Agent (skills_provider=%s)",
            config.maf_use_skills_provider,
        )
    return _agent


def get_faultdesk_session(call_id: str) -> Any:
    """Return a stored per-call MAF ``AgentSession`` for explicit reuse cases."""
    agent = get_faultdesk_agent()
    return get_thread_store().get_or_create(call_id, FAULTDESK_AGENT_SCOPE, agent)


async def run_faultdesk_agent(
    *,
    call_id: str,
    task: str,
    slot_store: Any = None,
    phase_state: Any = None,
    call_log: Any = None,
    handoff_summary: Optional[str] = None,
) -> str:
    """Run the single skill-enabled faultdesk agent for a task.

    Runtime objects are exposed to backend tools through task-local context.
    SkillsProvider still dynamically advertises skills and exposes
    ``load_skill`` / ``read_skill_resource`` for each run. We intentionally use
    a fresh MAF ``AgentSession`` per backend skill task because the full
    faultdesk path can hit Foundry Responses API 400s when reusing the stored
    session, while Voice Live plus SlotStore/CallLog hold the durable call
    context.
    """
    agent = get_faultdesk_agent()
    session = agent.create_session()

    instructions = ""
    if phase_state is not None and slot_store is not None:
        instructions = generate_instructions(phase_state, slot_store, handoff_summary=handoff_summary)

    prompt = (
        f"現在の通話ID: {call_id}\n"
        f"現在のオーケストレータ指示:\n{instructions}\n\n"
        f"実行タスク:\n{task}"
    )
    logger.info(
        "Running Faultdesk MAF Agent for call %s (task=%s)",
        call_id,
        task[:120],
    )
    context_token = set_faultdesk_tool_context(
        call_id=call_id,
        slot_store=slot_store,
        phase_state=phase_state,
        call_log=call_log,
    )
    try:
        result = await agent.run(prompt, session=session)
    finally:
        reset_faultdesk_tool_context(context_token)
    return str(result).strip()