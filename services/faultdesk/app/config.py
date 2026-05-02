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
    voice_live_api_key: str = Field(
        default="",
        description="Azure Voice Live API key. If omitted, Microsoft Entra ID is used.",
    )
    voice_live_model: str = Field(
        default="gpt-realtime",
        description="Azure Voice Live model identifier passed to connect(model=...).",
    )

    # Azure OpenAI fallback for MAF text inference
    azure_openai_endpoint: str = Field(
        default="",
        description="Azure OpenAI endpoint used only when Foundry project endpoint is not set.",
    )
    azure_openai_api_key: str = Field(
        default="",
        description="Azure OpenAI API key. If omitted, Microsoft Entra ID is used.",
    )
    azure_openai_api_version: str = Field(
        default="2024-10-21", description="Azure OpenAI API version"
    )
    azure_openai_model: str = Field(
        default="gpt-4o",
        description="Azure OpenAI text model or deployment name used when Foundry is not set.",
    )

    # Microsoft Foundry (preferred for the MAF skill agent when set)
    foundry_project_endpoint: str = Field(
        default="",
        description="Microsoft Foundry project endpoint. If set, MAF skill agents use FoundryChatClient.",
    )
    foundry_model: str = Field(
        default="",
        description="Microsoft Foundry model deployment name (e.g. gpt-4o).",
    )
    maf_use_skills_provider: bool = Field(
        default=True,
        description=(
            "Enable MAF SkillsProvider so file-based Agent Skills are dynamically "
            "advertised and loaded with load_skill/read_skill_resource."
        ),
    )

    # Optional real external APIs. Current adapters are in-process mocks.
    sf113_api_url: str = Field(default="", description="Optional real 113SF API URL")
    cultas_api_url: str = Field(default="", description="Optional real CULTAS API URL")
    ai_search_endpoint: str = Field(default="", description="Optional real AI Search endpoint")
    ai_search_api_key: str = Field(default="", description="Optional real AI Search API key")

    # Voice configuration
    voice_name: str = Field(default="ja-JP-NanamiNeural", description="Voice to use")
    voice_temperature: float = Field(default=0.7, description="Voice temperature")
    turn_detection_threshold: float = Field(default=0.5, description="Turn detection threshold")

    # Call logs
    call_logs_dir: Path = Field(default=Path("./logs/calls"), description="Directory for call logs")


# Global config instance
config = FaultdeskConfig()
