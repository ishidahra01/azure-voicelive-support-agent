"""
Identity verification skill.

Verifies customer identity using customer ID, name, address, or phone number.
"""

from typing import Any, Dict, Optional

from app.adapters import get_sf113_client
from .base import BaseSkill, SkillResult


class IdentitySkill(BaseSkill):
    """Skill for customer identity verification."""

    def __init__(self, call_id: str):
        """Initialize identity skill."""
        super().__init__(call_id, "identity")
        self.sf113 = get_sf113_client()
        self.attempts = 0
        self.max_attempts = 3

    async def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        Verify customer identity.

        Args:
            params: Dict with customer_id, name, address, phone

        Returns:
            SkillResult with verification status
        """
        self.attempts += 1
        self.logger.info(f"Identity verification attempt {self.attempts}/{self.max_attempts}")

        customer_id = params.get("customer_id")
        name = params.get("name")
        address = params.get("address")
        phone = params.get("phone")

        # Add to thread context
        self._add_to_thread("user", self._format_params_message(params))

        # Try customer ID first (most reliable)
        if customer_id:
            customer = await self.sf113.get_customer(customer_id)
            if customer:
                return SkillResult(
                    structured={
                        "verified": True,
                        "confidence": 1.0,
                        "customer_record": customer,
                        "verification_method": "customer_id",
                        "attempts": self.attempts,
                    },
                    conversational=f"ご本人確認できました。{customer['name']}様、{customer['address']}のご住所でお間違いございませんでしょうか。",
                    success=True,
                )
            else:
                return SkillResult(
                    structured={"verified": False, "attempts": self.attempts},
                    conversational="申し訳ございません。そのお客様番号が見つかりません。もう一度お客様番号をお伺いできますでしょうか。",
                    success=False,
                )

        # Try name + address combination
        if name:
            matches = await self.sf113.fuzzy_match_name(name)
            if matches:
                # If address provided, verify it
                if address and len(matches) > 0:
                    for match in matches:
                        addr_result = await self.sf113.verify_address(address, match)
                        if addr_result["match"] and addr_result["confidence"] > 0.7:
                            return SkillResult(
                                structured={
                                    "verified": True,
                                    "confidence": addr_result["confidence"],
                                    "customer_record": match,
                                    "verification_method": "name_address",
                                    "attempts": self.attempts,
                                },
                                conversational=f"ご本人確認できました。{match['name']}様ですね。お客様番号は{match['customer_id']}です。",
                                success=True,
                            )

                # Multiple matches, need disambiguation
                if len(matches) > 1:
                    return SkillResult(
                        structured={
                            "verified": False,
                            "candidates": matches,
                            "attempts": self.attempts,
                        },
                        conversational="同じお名前の方が複数いらっしゃいます。ご住所をお伺いできますでしょうか。",
                        success=False,
                    )

        # Max attempts reached
        if self.attempts >= self.max_attempts:
            return SkillResult(
                structured={
                    "verified": False,
                    "escalate": True,
                    "attempts": self.attempts,
                },
                conversational="申し訳ございません。ご本人確認ができませんでした。担当者におつなぎいたします。",
                success=False,
            )

        # Need more information
        return SkillResult(
            structured={"verified": False, "attempts": self.attempts},
            conversational="ご本人確認のため、お客様番号またはご住所をお伺いできますでしょうか。",
            success=False,
        )
