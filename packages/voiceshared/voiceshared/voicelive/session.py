"""
Voice Live SDK session wrapper.

Provides a higher-level abstraction over the Azure Voice Live SDK for creating
and managing real-time voice sessions.
"""

import json
import logging
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from azure.ai.voicelive.aio import VoiceLiveConnection, connect
from azure.ai.voicelive.models import (
    AudioEchoCancellation,
    AudioInputTranscriptionOptions,
    AudioNoiseReduction,
    AzureStandardVoice,
    FunctionTool,
    InputAudioFormat,
    Modality,
    OutputAudioFormat,
    RequestSession,
    ServerVad,
)
from azure.core.credentials import AzureKeyCredential
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)

_PLACEHOLDER_API_KEYS = {
    "your_voice_live_api_key_here",
    "your_azure_openai_api_key_here",
    "<key>",
}


def _has_api_key(api_key: Optional[str]) -> bool:
    return bool(api_key and api_key.strip() and api_key.strip() not in _PLACEHOLDER_API_KEYS)


def _normalize_tool_schema(tool: Dict[str, Any]) -> FunctionTool:
    """Convert local OpenAI-style tool schemas to Voice Live SDK FunctionTool."""
    function = tool.get("function", tool)
    return FunctionTool(
        name=function["name"],
        description=function.get("description"),
        parameters=function.get("parameters"),
    )


class VoiceSessionManager:
    """
    Manages Voice Live sessions with automatic reconnection and error handling.

    This class provides a wrapper around the Azure Voice Live SDK to simplify
    session management, tool registration, and event handling.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str] = None,
        use_managed_identity: bool = False,
    ):
        """
        Initialize the Voice Session Manager.

        Args:
            endpoint: Azure Voice Live endpoint URL
            api_key: API key for authentication. If omitted, Microsoft Entra ID is used.
            use_managed_identity: Force Microsoft Entra ID authentication.
        """
        self.endpoint = endpoint
        self.use_managed_identity = use_managed_identity
        self.event_handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._connection_context: Any = None

        if use_managed_identity or not _has_api_key(api_key):
            self.credential = DefaultAzureCredential()
        else:
            self.credential = AzureKeyCredential(api_key.strip())

        self.session: Optional[VoiceLiveConnection] = None
        self.session_id: Optional[str] = None

    async def create_session(
        self,
        model: str = "gpt-realtime",
        voice: str = "ja-JP-NanamiNeural",
        instructions: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        turn_detection: Optional[Dict[str, Any]] = None,
    ) -> VoiceLiveConnection:
        """
        Create a new Voice Live session.

        Args:
            model: Voice Live model identifier passed to connect(model=...)
            voice: The voice to use (default: ja-JP-NanamiNeural)
            instructions: System instructions for the agent
            tools: List of tool definitions
            temperature: Sampling temperature (0.0-1.0)
            turn_detection: Turn detection configuration

        Returns:
            VoiceLiveSession instance
        """
        # Configure voice
        voice_config = AzureStandardVoice(name=voice)

        # Configure turn detection (default: server VAD)
        if turn_detection is None:
            turn_detection_config = ServerVad(
                threshold=0.5,
                prefix_padding_ms=300,
                silence_duration_ms=500,
                create_response=True,
                interrupt_response=True,
                auto_truncate=True,
            )
        else:
            turn_detection_config = ServerVad(**turn_detection)

        session_config = RequestSession(
            model=model,
            modalities=[Modality.TEXT, Modality.AUDIO],
            voice=voice_config,
            instructions=instructions,
            tools=[_normalize_tool_schema(tool) for tool in tools or []],
            tool_choice="auto" if tools else None,
            temperature=temperature,
            turn_detection=turn_detection_config,
            input_audio_format=InputAudioFormat.PCM16,
            output_audio_format=OutputAudioFormat.PCM16,
            input_audio_sampling_rate=24000,
            input_audio_echo_cancellation=AudioEchoCancellation(),
            input_audio_noise_reduction=AudioNoiseReduction(type="azure_deep_noise_suppression"),
            input_audio_transcription=AudioInputTranscriptionOptions(model="azure-speech"),
        )

        self._connection_context = connect(
            endpoint=self.endpoint,
            credential=self.credential,
            model=model,
        )
        self.session = await self._connection_context.__aenter__()
        await self.session.session.update(session=session_config)
        self.session_id = "active"

        logger.info(f"Created Voice Live session: {self.session_id}")

        return self.session

    async def send_audio(self, audio_base64: str) -> None:
        """
        Send audio data to the session.

        Args:
            audio_base64: Base64-encoded PCM16 audio data
        """
        if not self.session:
            raise RuntimeError("No active session")

        await self.session.input_audio_buffer.append(audio=audio_base64)

    async def send_tool_result(self, call_id: str, result: Any) -> None:
        """Send a function call result back to Voice Live and request the next response."""
        if not self.session:
            raise RuntimeError("No active session")

        output = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        await self.session.conversation.item.create(
            item={
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            }
        )
        await self.session.response.create()

    async def events(self) -> AsyncIterator[Any]:
        """
        Iterate typed Voice Live server events for the session.
        """
        if not self.session:
            raise RuntimeError("No active session")

        async for event in self.session:
            yield event

    async def register_event_handler(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """
        Register an event handler for session events.

        Args:
            event_type: Type of event to handle (e.g., "transcript", "function_call")
            handler: Async function to handle the event
        """
        if not self.session:
            raise RuntimeError("No active session")

        self.event_handlers[event_type] = handler

    async def update_instructions(self, instructions: str) -> None:
        """
        Update the system instructions for the current session.

        Args:
            instructions: New instructions
        """
        if not self.session:
            raise RuntimeError("No active session")

        session_config = RequestSession(instructions=instructions)
        await self.session.session.update(session=session_config)
        logger.debug("Updated session instructions")

    async def close(self) -> None:
        """Close the session and clean up resources."""
        if self.session:
            try:
                if self._connection_context:
                    await self._connection_context.__aexit__(None, None, None)
                else:
                    await self.session.close()
                logger.info(f"Closed session: {self.session_id}")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
            finally:
                self.session = None
                self.session_id = None
                self._connection_context = None
        if isinstance(self.credential, DefaultAzureCredential):
            await self.credential.close()


async def create_voice_session(
    endpoint: str,
    api_key: Optional[str] = None,
    use_managed_identity: bool = False,
    **session_kwargs,
) -> VoiceSessionManager:
    """
    Convenience function to create and initialize a Voice Session Manager.

    Args:
        endpoint: Azure Voice Live endpoint URL
        api_key: API key for authentication. If omitted, Microsoft Entra ID is used.
        use_managed_identity: Force Microsoft Entra ID authentication
        **session_kwargs: Additional arguments for create_session()

    Returns:
        Initialized VoiceSessionManager with active session
    """
    manager = VoiceSessionManager(
        endpoint=endpoint,
        api_key=api_key,
        use_managed_identity=use_managed_identity,
    )

    await manager.create_session(**session_kwargs)

    return manager
