"""
Configuration for faultdesk service.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FaultdeskConfig(BaseSettings):
    """Configuration for faultdesk service."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Server configuration
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8001, description="Port to bind to")
    log_level: str = Field(default="INFO", description="Logging level")

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

    # External APIs
    sf113_api_url: str = Field(default="http://localhost:9001/api", description="113SF API URL")
    cultas_api_url: str = Field(default="http://localhost:9002/api", description="CULTAS API URL")
    ai_search_endpoint: str = Field(default="", description="AI Search endpoint")
    ai_search_api_key: str = Field(default="", description="AI Search API key")

    # Voice configuration
    voice_name: str = Field(default="ja-JP-NanamiNeural", description="Voice to use")
    voice_temperature: float = Field(default=0.7, description="Voice temperature")
    turn_detection_threshold: float = Field(default=0.5, description="Turn detection threshold")

    # Call logs
    call_logs_dir: Path = Field(default=Path("./logs/calls"), description="Directory for call logs")


# Global config instance
config = FaultdeskConfig()
