"""
Dynamic instructions generation.

Generates Voice Live instructions based on current phase and slot state.
"""

import logging
from typing import Optional

from app.orchestrator.phase_state import PhaseState
from app.phases import get_phase_description
from app.slots import PHASE_SLOTS, SlotStore

logger = logging.getLogger(__name__)


def generate_instructions(
    phase_state: PhaseState,
    slot_store: SlotStore,
    handoff_summary: Optional[str] = None,
) -> str:
    """
    Generate dynamic instructions for Voice Live agent.

    Args:
        phase_state: Current phase state
        slot_store: Slot store with current values
        handoff_summary: Summary from handoff (if available)

    Returns:
        Instructions string
    """
    current_phase = phase_state.current
    phase_desc = get_phase_description(current_phase)

    # Get pending slots for current phase
    pending_slots = slot_store.get_pending_slots(current_phase)
    pending_slots_text = _format_pending_slots(current_phase, pending_slots)

    # Get all filled slots
    filled_slots = slot_store.get_all_filled_slots()
    filled_slots_text = _format_filled_slots(filled_slots)

    # Build instructions
    instructions = f"""あなたは故障手配窓口の担当者です。明るく丁寧に、しかし要件は確実に確認してください。

【現在のフェーズ】 {current_phase} ({phase_desc})

【このフェーズの未確定項目】
{pending_slots_text}

【全フェーズの確定済み情報】
{filled_slots_text}

【ガイダンス】
- 未確定項目を順に自然な質問で埋めてください。1問1答を心がけ、長くなりすぎないこと
- お客様が話題を変えた場合は jump_to_phase ツールで該当フェーズに移ってください
- 情報が確定したら対応する Skill ツール (verify_identity / interview_fault / run_line_test / propose_visit_slots / confirm_visit / record_history) を呼んで記録してください
- このフェーズの required 項目がすべて埋まったら、次のフェーズへ進めて良いか一言確認してから jump_to_phase を呼んでください
- お客様が強く感情的、または対応困難な場合は handoff_to_operator を呼んでください
"""

    if handoff_summary:
        instructions += f"\n【引き継ぎサマリ（受付からの申し送り）】\n{handoff_summary}\n"

    return instructions


def _format_pending_slots(phase: str, pending_slot_names: list) -> str:
    """Format pending slots for display."""
    if not pending_slot_names:
        return "（すべて確定済み）"

    slot_defs = PHASE_SLOTS.get(phase, [])
    lines = []

    for slot_name in pending_slot_names:
        # Find slot definition
        slot_def = next((s for s in slot_defs if s.name == slot_name), None)
        if slot_def:
            lines.append(f"- {slot_name}: {slot_def.description} (必須)")

    return "\n".join(lines) if lines else "（なし）"


def _format_filled_slots(filled_slots: dict) -> str:
    """Format filled slots for display."""
    if not filled_slots:
        return "（まだ確定済み情報はありません）"

    lines = []

    for phase, slots in filled_slots.items():
        lines.append(f"[{phase}]")
        for slot_name, value in slots.items():
            # Format value for display
            if isinstance(value, bool):
                value_str = "はい" if value else "いいえ"
            elif isinstance(value, dict):
                value_str = str(value)[:50]  # Truncate long dicts
            else:
                value_str = str(value)

            lines.append(f"  - {slot_name}: {value_str}")

    return "\n".join(lines)
