"""Handoff package initialization."""

from .manager import HandoffManager
from .registry import DeskRegistry, desk_registry

__all__ = ["HandoffManager", "DeskRegistry", "desk_registry"]
