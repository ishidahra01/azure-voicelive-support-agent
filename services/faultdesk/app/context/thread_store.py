"""
Thread store for managing skill-specific AgentThread contexts.

Each skill maintains its own conversation context per call_id to avoid
context pollution between different business logic domains.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AgentThread:
    """
    Mock AgentThread for skill context management.

    In a real implementation with Microsoft Agent Framework, this would be
    the actual AgentThread class from the framework.
    """

    def __init__(self, thread_id: str):
        """
        Initialize thread.

        Args:
            thread_id: Unique thread identifier (call_id:skill_name)
        """
        self.thread_id = thread_id
        self.messages: list = []
        self.metadata: Dict = {}

    def add_message(self, role: str, content: str):
        """Add message to thread."""
        self.messages.append({"role": role, "content": content})

    def get_messages(self) -> list:
        """Get all messages in thread."""
        return self.messages.copy()

    def clear(self):
        """Clear thread messages."""
        self.messages.clear()


class ThreadStore:
    """
    Store and retrieve AgentThread instances for skills.

    Maintains separate conversation contexts for each skill within a call.
    """

    def __init__(self):
        """Initialize thread store."""
        self._threads: Dict[str, AgentThread] = {}

    def get_or_create(self, call_id: str, skill_name: str) -> AgentThread:
        """
        Get or create AgentThread for a skill.

        Args:
            call_id: Call identifier
            skill_name: Skill name (identity, interview, etc.)

        Returns:
            AgentThread instance
        """
        thread_id = f"{call_id}:{skill_name}"

        if thread_id not in self._threads:
            logger.info(f"Creating new thread: {thread_id}")
            self._threads[thread_id] = AgentThread(thread_id)
        else:
            logger.debug(f"Retrieving existing thread: {thread_id}")

        return self._threads[thread_id]

    def get(self, call_id: str, skill_name: str) -> Optional[AgentThread]:
        """
        Get existing AgentThread.

        Args:
            call_id: Call identifier
            skill_name: Skill name

        Returns:
            AgentThread instance or None if not found
        """
        thread_id = f"{call_id}:{skill_name}"
        return self._threads.get(thread_id)

    def remove(self, call_id: str, skill_name: Optional[str] = None):
        """
        Remove thread(s) for a call.

        Args:
            call_id: Call identifier
            skill_name: Optional skill name. If None, removes all threads for call.
        """
        if skill_name:
            thread_id = f"{call_id}:{skill_name}"
            if thread_id in self._threads:
                logger.info(f"Removing thread: {thread_id}")
                del self._threads[thread_id]
        else:
            # Remove all threads for this call
            prefix = f"{call_id}:"
            to_remove = [tid for tid in self._threads if tid.startswith(prefix)]
            for tid in to_remove:
                logger.info(f"Removing thread: {tid}")
                del self._threads[tid]

    def get_all_for_call(self, call_id: str) -> Dict[str, AgentThread]:
        """
        Get all threads for a call.

        Args:
            call_id: Call identifier

        Returns:
            Dict mapping skill_name to AgentThread
        """
        prefix = f"{call_id}:"
        threads = {}

        for thread_id, thread in self._threads.items():
            if thread_id.startswith(prefix):
                skill_name = thread_id[len(prefix) :]
                threads[skill_name] = thread

        return threads


# Global instance
_thread_store: Optional[ThreadStore] = None


def get_thread_store() -> ThreadStore:
    """Get or create global ThreadStore instance."""
    global _thread_store
    if _thread_store is None:
        _thread_store = ThreadStore()
    return _thread_store
