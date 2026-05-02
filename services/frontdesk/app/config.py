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
    voice_live_api_key: str = Field(
        default="",
        description="Azure Voice Live API key. If omitted, Microsoft Entra ID is used.",
    )
    voice_live_model: str = Field(
        default="gpt-realtime",
        description="Azure Voice Live model identifier passed to connect(model=...).",
    )

    # Desk service URLs
    fault_desk_ws_url: str = Field(
        default="ws://localhost:8001/ws/desk", description="Faultdesk WebSocket URL"
    )
    billing_desk_ws_url: str = Field(
        default="", description="Optional Billingdesk WebSocket URL"
    )
    general_desk_ws_url: str = Field(
        default="", description="Optional Generaldesk WebSocket URL"
    )

    # Voice configuration
    voice_name: str = Field(default="ja-JP-NanamiNeural", description="Voice to use")
    voice_temperature: float = Field(default=0.7, description="Voice temperature")
    turn_detection_threshold: float = Field(default=0.5, description="Turn detection threshold")


# Global config instance
config = FrontdeskConfig()
