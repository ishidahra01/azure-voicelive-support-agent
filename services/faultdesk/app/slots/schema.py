"""
Slot schema definitions.

Defines all slots used across phases with their types, validators, and requirements.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel


class SlotStatus(str, Enum):
    """Status of a slot."""

    PENDING = "pending"
    FILLED = "filled"
    INVALID = "invalid"


class Slot(BaseModel):
    """Definition of a slot."""

    name: str
    required: bool
    type: str  # "str", "bool", "dict", "list", etc.
    description: str = ""
    validator: Optional[str] = None  # Name of validator function
    default: Any = None


# Slot definitions by phase
PHASE_SLOTS: Dict[str, List[Slot]] = {
    "intake": [
        Slot(
            name="greeting_done",
            required=True,
            type="bool",
            description="挨拶が完了したか",
        ),
        Slot(
            name="understood_intent",
            required=True,
            type="bool",
            description="お客様の意図を理解したか",
        ),
    ],
    "identity": [
        Slot(
            name="customer_id",
            required=True,
            type="str",
            description="8桁のお客様番号",
            validator="is_8digit",
        ),
        Slot(
            name="name_match",
            required=True,
            type="bool",
            description="氏名が一致したか",
        ),
        Slot(
            name="address_match",
            required=True,
            type="bool",
            description="住所が一致したか",
        ),
        Slot(
            name="contact_phone",
            required=True,
            type="str",
            description="連絡先電話番号",
        ),
        Slot(
            name="verification_status",
            required=True,
            type="str",
            description="本人確認結果",
        ),
    ],
    "interview": [
        Slot(
            name="fault_symptom",
            required=True,
            type="str",
            description="故障症状の説明",
        ),
        Slot(
            name="fault_started_at",
            required=True,
            type="str",
            description="故障発生時期",
        ),
        Slot(
            name="indoor_env",
            required=True,
            type="dict",
            description="室内機器の状況",
        ),
        Slot(
            name="line_test_result",
            required=False,
            type="dict",
            description="回線試験結果",
        ),
        Slot(
            name="suspected_cause",
            required=False,
            type="str",
            description="推定原因",
        ),
        Slot(
            name="diagnosis_complete",
            required=True,
            type="bool",
            description="診断が完了したか",
        ),
    ],
    "visit": [
        Slot(
            name="visit_required",
            required=True,
            type="bool",
            description="訪問修理が必要か",
        ),
        Slot(
            name="visit_candidates",
            required=True,
            type="list",
            description="候補日時リスト",
        ),
        Slot(
            name="customer_preference",
            required=False,
            type="dict",
            description="お客様の希望日時",
        ),
        Slot(
            name="visit_confirmed",
            required=True,
            type="dict",
            description="確定した訪問予約",
        ),
        Slot(
            name="dispatch_id",
            required=True,
            type="str",
            description="手配番号",
        ),
    ],
    "closing": [
        Slot(
            name="resolution_status",
            required=True,
            type="str",
            description="解決状況",
        ),
        Slot(
            name="customer_satisfied",
            required=True,
            type="bool",
            description="お客様が納得したか",
        ),
        Slot(
            name="history_recorded",
            required=True,
            type="bool",
            description="履歴を記録したか",
        ),
        Slot(
            name="followup_needed",
            required=False,
            type="bool",
            description="フォローアップが必要か",
        ),
        Slot(
            name="closing_complete",
            required=True,
            type="bool",
            description="クロージング完了したか",
        ),
    ],
}


# Validator functions
def is_8digit(value: str) -> bool:
    """Validate 8-digit customer ID."""
    return value.isdigit() and len(value) == 8


VALIDATORS: Dict[str, Callable[[Any], bool]] = {
    "is_8digit": is_8digit,
}


def get_slot_definition(phase: str, slot_name: str) -> Optional[Slot]:
    """Get slot definition."""
    slots = PHASE_SLOTS.get(phase, [])
    for slot in slots:
        if slot.name == slot_name:
            return slot
    return None


def validate_slot_value(slot: Slot, value: Any) -> tuple[bool, Optional[str]]:
    """
    Validate slot value.

    Returns:
        (is_valid, error_message)
    """
    # Check if validator exists
    if slot.validator:
        validator = VALIDATORS.get(slot.validator)
        if validator:
            try:
                if not validator(value):
                    return False, f"Validation failed for {slot.name}"
            except Exception as e:
                return False, f"Validator error: {str(e)}"

    return True, None
