"""
Voice Live SDK session wrapper.

Provides a higher-level abstraction over the Azure Voice Live SDK for creating
and managing real-time voice sessions.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from azure.ai.voicelive import (
    VoiceLiveClient,
    VoiceLiveSession,
    VoiceLiveSessionConfig,
)
from azure.ai.voicelive.models import (
    AudioFormat,
    AudioStreamConfig,
    SessionOptions,
    TurnDetection,
    VoiceConfig,
)
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


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
            api_key: API key for authentication (if not using managed identity)
            use_managed_identity: Use Azure Managed Identity for authentication
        """
        self.endpoint = endpoint
        self.use_managed_identity = use_managed_identity

        if use_managed_identity:
            self.credential = DefaultAzureCredential()
        elif api_key:
            self.credential = AzureKeyCredential(api_key)
        else:
            raise ValueError("Either api_key or use_managed_identity must be provided")

        self.client = VoiceLiveClient(endpoint=endpoint, credential=self.credential)
        self.session: Optional[VoiceLiveSession] = None
        self.session_id: Optional[str] = None

    async def create_session(
        self,
        model: str = "gpt-4o-realtime-preview",
        voice: str = "ja-JP-NanamiNeural",
        instructions: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        turn_detection: Optional[Dict[str, Any]] = None,
    ) -> VoiceLiveSession:
        """
        Create a new Voice Live session.

        Args:
            model: The model to use (default: gpt-4o-realtime-preview)
            voice: The voice to use (default: ja-JP-NanamiNeural)
            instructions: System instructions for the agent
            tools: List of tool definitions
            temperature: Sampling temperature (0.0-1.0)
            turn_detection: Turn detection configuration

        Returns:
            VoiceLiveSession instance
        """
        # Configure audio format (PCM16, 24kHz, mono)
        audio_config = AudioStreamConfig(
            format=AudioFormat.PCM16,
            sample_rate=24000,
            channels=1,
        )

        # Configure voice
        voice_config = VoiceConfig(voice=voice)

        # Configure turn detection (default: server VAD)
        if turn_detection is None:
            turn_detection_config = TurnDetection(
                type="server_vad",
                threshold=0.5,
                prefix_padding_ms=300,
                silence_duration_ms=500,
            )
        else:
            turn_detection_config = TurnDetection(**turn_detection)

        # Create session options
        session_options = SessionOptions(
            model=model,
            voice=voice_config,
            instructions=instructions,
            tools=tools or [],
            temperature=temperature,
            turn_detection=turn_detection_config,
            audio_input=audio_config,
            audio_output=audio_config,
        )

        # Create session config
        session_config = VoiceLiveSessionConfig(options=session_options)

        # Create the session
        self.session = await self.client.create_session(config=session_config)
        self.session_id = self.session.session_id

        logger.info(f"Created Voice Live session: {self.session_id}")

        return self.session

    async def send_audio(self, audio_data: bytes) -> None:
        """
        Send audio data to the session.

        Args:
            audio_data: PCM16 audio data
        """
        if not self.session:
            raise RuntimeError("No active session")

        await self.session.send_audio(audio_data)

    async def receive_audio(self) -> Optional[bytes]:
        """
        Receive audio data from the session.

        Returns:
            PCM16 audio data or None
        """
        if not self.session:
            raise RuntimeError("No active session")

        return await self.session.receive_audio()

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

        self.session.on(event_type, handler)

    async def update_instructions(self, instructions: str) -> None:
        """
        Update the system instructions for the current session.

        Args:
            instructions: New instructions
        """
        if not self.session:
            raise RuntimeError("No active session")

        await self.session.update(instructions=instructions)
        logger.debug("Updated session instructions")

    async def close(self) -> None:
        """Close the session and clean up resources."""
        if self.session:
            try:
                await self.session.close()
                logger.info(f"Closed session: {self.session_id}")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
            finally:
                self.session = None
                self.session_id = None


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
        api_key: API key for authentication
        use_managed_identity: Use Azure Managed Identity
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
