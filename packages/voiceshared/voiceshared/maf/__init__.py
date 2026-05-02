"""
Microsoft Agent Framework integration helpers.

Exposes a ChatClient factory used by skill-based agents.
"""

from .client import create_chat_client

__all__ = ["create_chat_client"]
