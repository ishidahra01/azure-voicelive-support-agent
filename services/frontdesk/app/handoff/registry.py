"""
Desk endpoint registry.

Manages the mapping of desk names to WebSocket URLs.
"""

import logging
from typing import Dict, Optional

from app.config import config

logger = logging.getLogger(__name__)


class DeskRegistry:
    """Registry of desk service endpoints."""

    def __init__(self):
        self._desks: Dict[str, str] = {}
        for desk_name, ws_url in {
            "fault": config.fault_desk_ws_url,
            "billing": config.billing_desk_ws_url,
            "general": config.general_desk_ws_url,
        }.items():
            if ws_url:
                self._desks[desk_name] = ws_url

    def get_desk_url(self, desk_name: str) -> Optional[str]:
        """
        Get WebSocket URL for a desk service.

        Args:
            desk_name: Name of the desk ('fault', 'billing', 'general')

        Returns:
            WebSocket URL or None if not found
        """
        url = self._desks.get(desk_name)
        if url:
            logger.debug(f"Found desk URL for {desk_name}: {url}")
        else:
            logger.warning(f"No desk URL found for {desk_name}")
        return url

    def register_desk(self, desk_name: str, ws_url: str):
        """Register a new desk service."""
        self._desks[desk_name] = ws_url
        logger.info(f"Registered desk {desk_name}: {ws_url}")

    def list_desks(self) -> Dict[str, str]:
        """List all registered desks."""
        return self._desks.copy()


# Global registry instance
desk_registry = DeskRegistry()
