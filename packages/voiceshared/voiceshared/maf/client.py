"""
Microsoft Agent Framework ChatClient factory.

Returns a Microsoft Agent Framework ``ChatClient`` for building skill agents.

Resolution order:

1. If ``foundry_project_endpoint`` is set, returns a ``FoundryChatClient`` (requires
   ``agent-framework-foundry`` to be installed).
2. Otherwise returns an ``OpenAIChatClient`` configured for Azure OpenAI.

Authentication: when an API key is provided it is used directly, otherwise
Microsoft Entra ID via ``DefaultAzureCredential`` is used (keyless).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from agent_framework.openai import OpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

_PLACEHOLDER_API_KEYS = {
    "your_voice_live_api_key_here",
    "your_azure_openai_api_key_here",
    "<key>",
    "",
}


def _has_api_key(api_key: Optional[str]) -> bool:
    return bool(api_key and api_key.strip() and api_key.strip() not in _PLACEHOLDER_API_KEYS)


def create_chat_client(
    *,
    azure_openai_endpoint: Optional[str] = None,
    azure_openai_api_key: Optional[str] = None,
    azure_openai_api_version: Optional[str] = None,
    azure_openai_model: Optional[str] = None,
    foundry_project_endpoint: Optional[str] = None,
    foundry_model: Optional[str] = None,
) -> Any:
    """Create a Microsoft Agent Framework ChatClient.

    Prefers Foundry when ``foundry_project_endpoint`` is provided; otherwise uses
    Azure OpenAI via the OpenAI Responses API client. Falls back to Microsoft
    Entra ID (DefaultAzureCredential) when no API key is supplied.
    """
    if foundry_project_endpoint:
        try:
            from agent_framework.foundry import FoundryChatClient  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError(
                "FOUNDRY_PROJECT_ENDPOINT is set but the 'agent-framework-foundry' "
                "package is not installed. Install it to use Foundry chat clients."
            ) from exc

        logger.info("Creating FoundryChatClient (model=%s)", foundry_model or "<env default>")
        kwargs: dict[str, Any] = {
            "project_endpoint": foundry_project_endpoint,
            "credential": DefaultAzureCredential(),
        }
        if foundry_model:
            kwargs["model"] = foundry_model
        return FoundryChatClient(**kwargs)

    if not azure_openai_endpoint:
        raise RuntimeError(
            "Either FOUNDRY_PROJECT_ENDPOINT or AZURE_OPENAI_ENDPOINT must be configured "
            "to create a Microsoft Agent Framework ChatClient."
        )

    if _has_api_key(azure_openai_api_key):
        logger.info(
            "Creating OpenAIChatClient (Azure key auth, model=%s)",
            azure_openai_model or "<env default>",
        )
        kwargs = {
            "azure_endpoint": azure_openai_endpoint,
            "api_key": azure_openai_api_key.strip(),  # type: ignore[union-attr]
        }
        if azure_openai_api_version:
            kwargs["api_version"] = azure_openai_api_version
        if azure_openai_model:
            kwargs["model"] = azure_openai_model
        return OpenAIChatCompletionClient(**kwargs)

    logger.info(
        "Creating OpenAIChatClient (Azure Entra ID auth, model=%s)",
        azure_openai_model or "<env default>",
    )
    kwargs = {
        "azure_endpoint": azure_openai_endpoint,
        "credential": DefaultAzureCredential(),
    }
    if azure_openai_api_version:
        kwargs["api_version"] = azure_openai_api_version
    if azure_openai_model:
        kwargs["model"] = azure_openai_model
    return OpenAIChatCompletionClient(**kwargs)
