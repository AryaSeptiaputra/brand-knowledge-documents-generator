"""Application configuration loaded from environment variables."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for API, local model, sessions, and uploads."""

    model_config = SettingsConfigDict(env_prefix="BKDG_", extra="ignore")

    log_format: Literal["text", "json"] = "text"
    ollama_host: str = ""
    model_name: str = "gemma4:26b-a4b-it-qat"
    temperature: float = 0.0
    num_ctx: int = 8192
    use_llm: bool = False
    max_retries: int = 1
    max_logo_bytes: int = 5 * 1024 * 1024
    max_yaml_bytes: int = 1024 * 1024
    max_yaml_nodes: int = 20_000
    session_ttl_minutes: int = 60
