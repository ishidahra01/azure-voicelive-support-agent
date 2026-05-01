"""
Slot store implementation.

Manages slot values across phases with persistence.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.slots.schema import PHASE_SLOTS, SlotStatus, get_slot_definition, validate_slot_value

logger = logging.getLogger(__name__)


class SlotStore:
    """
    Store for slot values across all phases.

    Maintains slot state and provides query methods.
    """

    def __init__(self, call_id: str):
        self.call_id = call_id
        self.data: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # Initialize all phases
        for phase_name in PHASE_SLOTS.keys():
            self.data[phase_name] = {}

    def set(
        self,
        phase: str,
        slot_name: str,
        value: Any,
        status: SlotStatus = SlotStatus.FILLED,
    ):
        """
        Set a slot value.

        Args:
            phase: Phase name
            slot_name: Slot name
            value: Slot value
            status: Slot status
        """
        if phase not in self.data:
            self.data[phase] = {}

        # Get slot definition for validation
        slot_def = get_slot_definition(phase, slot_name)
        if slot_def and status == SlotStatus.FILLED:
            is_valid, error = validate_slot_value(slot_def, value)
            if not is_valid:
                logger.warning(f"Invalid slot value for {phase}.{slot_name}: {error}")
                status = SlotStatus.INVALID

        self.data[phase][slot_name] = {
            "value": value,
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat(),
        }

        logger.debug(f"Set slot {phase}.{slot_name} = {value} ({status.value})")

    def get(self, phase: str, slot_name: str) -> Any:
        """Get slot value."""
        return self.data.get(phase, {}).get(slot_name, {}).get("value")

    def get_status(self, phase: str, slot_name: str) -> Optional[SlotStatus]:
        """Get slot status."""
        status_str = self.data.get(phase, {}).get(slot_name, {}).get("status")
        return SlotStatus(status_str) if status_str else None

    def is_filled(self, phase: str, slot_name: str) -> bool:
        """Check if slot is filled."""
        return self.get_status(phase, slot_name) == SlotStatus.FILLED

    def get_pending_slots(self, phase: str) -> List[str]:
        """Get list of pending required slots in a phase."""
        slot_defs = PHASE_SLOTS.get(phase, [])
        pending = []

        for slot_def in slot_defs:
            if slot_def.required and not self.is_filled(phase, slot_def.name):
                pending.append(slot_def.name)

        return pending

    def is_phase_complete(self, phase: str) -> bool:
        """Check if all required slots in a phase are filled."""
        return len(self.get_pending_slots(phase)) == 0

    def get_all_filled_slots(self) -> Dict[str, Dict[str, Any]]:
        """Get all filled slots across all phases."""
        result = {}

        for phase, slots in self.data.items():
            phase_filled = {}
            for slot_name, slot_data in slots.items():
                if slot_data.get("status") == SlotStatus.FILLED.value:
                    phase_filled[slot_name] = slot_data.get("value")

            if phase_filled:
                result[phase] = phase_filled

        return result

    def export(self) -> Dict[str, Any]:
        """Export all slot data."""
        return {
            "call_id": self.call_id,
            "phases": self.data,
            "exported_at": datetime.utcnow().isoformat(),
        }
