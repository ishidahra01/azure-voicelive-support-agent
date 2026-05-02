"""
Microsoft Agent Framework ``AgentSession`` store.

Sessions are keyed by ``call_id`` plus an agent scope for callers that need
explicitly reused MAF context. Faultdesk skill tasks currently use fresh
sessions in ``run_faultdesk_agent``; durable call state lives in Voice Live,
SlotStore, and CallLog.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ThreadStore:
    """Store and retrieve MAF ``AgentSession`` instances per (call_id, scope)."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Any] = {}

    @staticmethod
    def _key(call_id: str, scope: str) -> str:
        return f"{call_id}:{scope}"

    def get_or_create(self, call_id: str, scope: str, agent: Any) -> Any:
        """Return the MAF ``AgentSession`` for the scope, creating it if missing.

        The session is produced via ``agent.create_session()`` so that callers
        can opt into persisted MAF context across turns when appropriate.
        """
        key = self._key(call_id, scope)
        session = self._sessions.get(key)
        if session is None:
            logger.info("Creating new MAF AgentSession: %s", key)
            session = agent.create_session()
            self._sessions[key] = session
        else:
            logger.debug("Reusing MAF AgentSession: %s", key)
        return session

    def get(self, call_id: str, scope: str) -> Optional[Any]:
        return self._sessions.get(self._key(call_id, scope))

    def remove(self, call_id: str, scope: Optional[str] = None) -> None:
        if scope:
            key = self._key(call_id, scope)
            if key in self._sessions:
                logger.info("Removing MAF AgentSession: %s", key)
                del self._sessions[key]
            return

        prefix = f"{call_id}:"
        for key in [k for k in self._sessions if k.startswith(prefix)]:
            logger.info("Removing MAF AgentSession: %s", key)
            del self._sessions[key]

    def get_all_for_call(self, call_id: str) -> Dict[str, Any]:
        prefix = f"{call_id}:"
        return {
            key[len(prefix):]: session
            for key, session in self._sessions.items()
            if key.startswith(prefix)
        }


_thread_store: Optional[ThreadStore] = None


def get_thread_store() -> ThreadStore:
    """Return the process-wide ``ThreadStore`` singleton."""
    global _thread_store
    if _thread_store is None:
        _thread_store = ThreadStore()
    return _thread_store
