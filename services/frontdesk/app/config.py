"""
Configuration for frontdesk service.

Loads environment variables and provides typed configuration objects.
"""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FrontdeskConfig(BaseSettings):
    """Configuration for frontdesk service."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Server configuration
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to bind to")
    log_level: str = Field(default="INFO", description="Logging level")
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS allowed origins",
    )

    # Azure Voice Live API
    voice_live_endpoint: str = Field(..., description="Azure Voice Live API endpoint")
    voice_live_api_key: str = Field(..., description="Azure Voice Live API key")

    # Azure OpenAI / Foundry
    azure_openai_endpoint: str = Field(..., description="Azure OpenAI endpoint")
    azure_openai_api_key: str = Field(..., description="Azure OpenAI API key")
    azure_openai_api_version: str = Field(
        default="2024-10-21", description="Azure OpenAI API version"
    )
    azure_openai_model: str = Field(
        default="gpt-4o-realtime-preview", description="Model for Voice Live"
    )

    # Desk service URLs
    fault_desk_ws_url: str = Field(
        default="ws://localhost:8001/ws/desk", description="Faultdesk WebSocket URL"
    )
    billing_desk_ws_url: str = Field(
        default="ws://localhost:8002/ws/desk", description="Billingdesk WebSocket URL"
    )
    general_desk_ws_url: str = Field(
        default="ws://localhost:8003/ws/desk", description="Generaldesk WebSocket URL"
    )

    # Voice configuration
    voice_name: str = Field(default="ja-JP-NanamiNeural", description="Voice to use")
    voice_temperature: float = Field(default=0.7, description="Voice temperature")
    turn_detection_threshold: float = Field(
        default=0.5, description="Turn detection threshold"
    )


# Global config instance
config = FrontdeskConfig()
