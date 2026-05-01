"""
113SF system adapter (Mock implementation).

Provides customer database and dispatch management functionality.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SF113Client:
    """Mock 113SF system client."""

    def __init__(self):
        """Initialize client with mock data."""
        self._customers = {
            "12345678": {
                "customer_id": "12345678",
                "name": "山田太郎",
                "name_kana": "ヤマダタロウ",
                "address": "東京都渋谷区渋谷1-1-1",
                "phone": "03-1234-5678",
                "contract_type": "フレッツ光ネクスト",
                "area_code": "03",
            },
            "87654321": {
                "customer_id": "87654321",
                "name": "佐藤花子",
                "name_kana": "サトウハナコ",
                "address": "大阪府大阪市北区梅田2-2-2",
                "phone": "06-9876-5432",
                "contract_type": "フレッツ光ネクスト",
                "area_code": "06",
            },
        }
        self._dispatch_orders: Dict[str, Dict] = {}

    async def get_customer(self, customer_id: str) -> Optional[Dict]:
        """
        Retrieve customer record by customer ID.

        Args:
            customer_id: 8-digit customer ID

        Returns:
            Customer record or None if not found
        """
        logger.info(f"SF113: Getting customer {customer_id}")
        return self._customers.get(customer_id)

    async def fuzzy_match_name(
        self, name: str, candidates: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        Fuzzy match customer name.

        Args:
            name: Name to match
            candidates: Optional list of candidate records to filter

        Returns:
            List of matching customer records with confidence scores
        """
        logger.info(f"SF113: Fuzzy matching name '{name}'")

        if candidates is None:
            candidates = list(self._customers.values())

        matches = []
        for customer in candidates:
            # Simple substring matching for demo
            if name in customer["name"] or name in customer["name_kana"]:
                matches.append({**customer, "match_confidence": 0.9})
            elif any(
                part in customer["name"]
                for part in name.split()
                if len(part) > 1
            ):
                matches.append({**customer, "match_confidence": 0.7})

        return sorted(matches, key=lambda x: x["match_confidence"], reverse=True)

    async def verify_address(
        self, address: str, customer_record: Dict
    ) -> Dict:
        """
        Verify if address matches customer record.

        Args:
            address: Address to verify
            customer_record: Customer record to check against

        Returns:
            Verification result with confidence
        """
        logger.info(f"SF113: Verifying address '{address}'")

        customer_address = customer_record.get("address", "")

        # Simple matching logic for demo
        if address == customer_address:
            return {"match": True, "confidence": 1.0}

        # Partial match
        common_parts = set(address.split()) & set(customer_address.split())
        if len(common_parts) >= 2:
            return {
                "match": True,
                "confidence": len(common_parts) / max(
                    len(address.split()), len(customer_address.split())
                ),
            }

        return {"match": False, "confidence": 0.0}

    async def run_line_test(
        self, customer_id: str, test_type: str = "basic"
    ) -> Dict:
        """
        Execute remote line test.

        Args:
            customer_id: Customer ID
            test_type: Test type (basic, extended, full)

        Returns:
            Test results
        """
        logger.info(f"SF113: Running {test_type} line test for {customer_id}")

        test_id = f"LT-{uuid.uuid4().hex[:8].upper()}"

        # Mock test results (randomly vary for demo)
        import random

        line_ok = random.choice([True, False])

        if line_ok:
            return {
                "test_id": test_id,
                "customer_id": customer_id,
                "test_type": test_type,
                "executed_at": datetime.utcnow().isoformat(),
                "line_status": "ok",
                "results": {
                    "snr": 45.2,
                    "attenuation": 12.5,
                    "error_rate": 0.001,
                    "ng_segments": [],
                },
            }
        else:
            return {
                "test_id": test_id,
                "customer_id": customer_id,
                "test_type": test_type,
                "executed_at": datetime.utcnow().isoformat(),
                "line_status": "ng",
                "results": {
                    "snr": 12.1,
                    "attenuation": 58.3,
                    "error_rate": 0.125,
                    "ng_segments": ["segment_a", "segment_c"],
                },
            }

    async def get_visit_slots(
        self,
        area_code: str,
        work_type: str = "fault_repair",
        date_range: int = 7,
    ) -> List[Dict]:
        """
        Get available visit time slots.

        Args:
            area_code: Area code for dispatch
            work_type: Type of work
            date_range: Number of days to search

        Returns:
            List of available slots
        """
        logger.info(
            f"SF113: Getting visit slots for area {area_code}, work_type {work_type}"
        )

        slots = []
        base_date = datetime.now()

        # Generate mock slots for next few days
        for day_offset in range(1, min(date_range, 5)):
            slot_date = base_date + timedelta(days=day_offset)
            date_str = slot_date.strftime("%Y-%m-%d")

            # Morning slot
            slots.append({
                "slot_id": f"SLOT-{date_str}-AM",
                "date": date_str,
                "time_range": "09:00-12:00",
                "available": True,
                "priority": day_offset,
            })

            # Afternoon slot
            slots.append({
                "slot_id": f"SLOT-{date_str}-PM",
                "date": date_str,
                "time_range": "13:00-17:00",
                "available": True,
                "priority": day_offset,
            })

        return slots

    async def book_visit(
        self, customer_id: str, slot_id: str, notes: str = ""
    ) -> Dict:
        """
        Book visit appointment and create dispatch order.

        Args:
            customer_id: Customer ID
            slot_id: Selected slot ID
            notes: Optional notes

        Returns:
            Dispatch order details
        """
        logger.info(f"SF113: Booking visit for customer {customer_id}, slot {slot_id}")

        dispatch_id = f"DS-{uuid.uuid4().hex[:6].upper()}"

        # Extract date and time from slot_id
        parts = slot_id.split("-")
        date_str = "-".join(parts[1:4])  # YYYY-MM-DD
        time_period = parts[4] if len(parts) > 4 else "AM"

        dispatch_order = {
            "dispatch_id": dispatch_id,
            "customer_id": customer_id,
            "slot_id": slot_id,
            "date": date_str,
            "time_range": "09:00-12:00" if time_period == "AM" else "13:00-17:00",
            "work_type": "fault_repair",
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat(),
            "notes": notes,
            "technician_name": "田中一郎",
            "contact_phone": "0120-116-116",
        }

        self._dispatch_orders[dispatch_id] = dispatch_order
        return dispatch_order

    async def post_history(
        self, customer_id: str, history_data: Dict
    ) -> Dict:
        """
        Post interaction history to 113SF.

        Args:
            customer_id: Customer ID
            history_data: History record data

        Returns:
            Created history record
        """
        logger.info(f"SF113: Posting history for customer {customer_id}")

        history_id = f"HIS-{uuid.uuid4().hex[:8].upper()}"

        return {
            "history_id": history_id,
            "customer_id": customer_id,
            "recorded_at": datetime.utcnow().isoformat(),
            "success": True,
            **history_data,
        }


# Global instance
_sf113_client: Optional[SF113Client] = None


def get_sf113_client() -> SF113Client:
    """Get or create SF113 client instance."""
    global _sf113_client
    if _sf113_client is None:
        _sf113_client = SF113Client()
    return _sf113_client
