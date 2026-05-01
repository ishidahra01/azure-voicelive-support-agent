"""
CULTAS system adapter (Mock implementation).

Provides AI-powered diagnosis and device information functionality.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CultasClient:
    """Mock CULTAS system client."""

    def __init__(self):
        """Initialize client."""
        pass

    async def diagnose_symptom(self, symptom: str, context: Optional[Dict] = None) -> Dict:
        """
        AI-powered fault diagnosis based on symptoms.

        Args:
            symptom: Fault symptom description
            context: Additional context (device info, test results, etc.)

        Returns:
            Diagnosis result
        """
        logger.info(f"CULTAS: Diagnosing symptom '{symptom}'")

        # Simple keyword-based mock logic
        symptom_lower = symptom.lower()

        if "繋がらない" in symptom or "接続できない" in symptom or "ネット" in symptom:
            return {
                "suspected_cause": "line",
                "confidence": 0.75,
                "urgency": "high",
                "recommended_questions": [
                    "ルーターのランプ状態を確認してください",
                    "他の機器でもインターネットに接続できませんか",
                    "いつ頃から症状が発生していますか",
                ],
                "recommended_action": "run_line_test",
            }
        elif "遅い" in symptom or "スピード" in symptom:
            return {
                "suspected_cause": "indoor_wiring",
                "confidence": 0.6,
                "urgency": "medium",
                "recommended_questions": [
                    "有線接続と無線接続のどちらですか",
                    "ルーターと機器の距離はどのくらいですか",
                ],
                "recommended_action": "interview_more",
            }
        else:
            return {
                "suspected_cause": "unknown",
                "confidence": 0.3,
                "urgency": "medium",
                "recommended_questions": [
                    "具体的にどのような症状ですか",
                ],
                "recommended_action": "interview_more",
            }

    async def get_device_info(self, customer_id: str) -> Dict:
        """
        Get device information for customer.

        Args:
            customer_id: Customer ID

        Returns:
            Device information
        """
        logger.info(f"CULTAS: Getting device info for customer {customer_id}")

        # Mock device info
        return {
            "customer_id": customer_id,
            "devices": [
                {
                    "type": "onu",
                    "model": "GE-ONU",
                    "serial": "ONU123456",
                    "status": "online",
                },
                {
                    "type": "router",
                    "model": "RT-500KI",
                    "serial": "RT789012",
                    "status": "online",
                },
            ],
        }

    async def interpret_test(self, test_results: Dict) -> Dict:
        """
        Interpret line test results.

        Args:
            test_results: Raw line test results

        Returns:
            Interpretation and recommended action
        """
        logger.info("CULTAS: Interpreting line test results")

        line_status = test_results.get("line_status", "unknown")
        ng_segments = test_results.get("results", {}).get("ng_segments", [])

        if line_status == "ng" and ng_segments:
            return {
                "interpretation": "line_fault",
                "severity": "high",
                "location": "external_line",
                "recommended_action": "dispatch",
                "explanation": "回線に問題が検出されました。技術者による訪問修理が必要です。",
            }
        elif line_status == "ok":
            return {
                "interpretation": "customer_equipment",
                "severity": "medium",
                "location": "indoor",
                "recommended_action": "customer_reset",
                "explanation": "回線には問題ありません。お客様宅内の機器を再起動してみてください。",
            }
        else:
            return {
                "interpretation": "unclear",
                "severity": "medium",
                "location": "unknown",
                "recommended_action": "monitor",
                "explanation": "明確な問題は検出されませんでした。様子を見てください。",
            }

    async def filter_slots(
        self, slots: List[Dict], urgency: str, preferences: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Filter and prioritize visit slots based on business rules.

        Args:
            slots: Available slots
            urgency: Urgency level (high, medium, low)
            preferences: Customer preferences

        Returns:
            Filtered and sorted slots
        """
        logger.info(f"CULTAS: Filtering slots with urgency={urgency}")

        # Sort by priority (lower = better)
        sorted_slots = sorted(slots, key=lambda x: x.get("priority", 99))

        # For high urgency, only return earliest slots
        if urgency == "high":
            return sorted_slots[:3]

        # For medium/low, return more options
        return sorted_slots[:5]

    async def categorize_issue(self, summary: str) -> Dict:
        """
        Categorize issue for analytics.

        Args:
            summary: Issue summary

        Returns:
            Category and tags
        """
        logger.info("CULTAS: Categorizing issue")

        # Simple keyword-based categorization
        if "繋がらない" in summary or "接続" in summary:
            category = "connectivity"
            tags = ["internet", "connection_failure"]
        elif "遅い" in summary:
            category = "performance"
            tags = ["internet", "slow_speed"]
        else:
            category = "other"
            tags = ["inquiry"]

        return {
            "category": category,
            "tags": tags,
            "severity": "medium",
        }


# Global instance
_cultas_client: Optional[CultasClient] = None


def get_cultas_client() -> CultasClient:
    """Get or create CULTAS client instance."""
    global _cultas_client
    if _cultas_client is None:
        _cultas_client = CultasClient()
    return _cultas_client
