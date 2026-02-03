"""Global settings loaded from environment variables and .env file."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais do sistema.

    Valores são carregados do arquivo .env e podem ser sobrescritos
    por variáveis de ambiente. Campos sem default são obrigatórios.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Keys
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    openai_api_key: str | None = Field(None, description="OpenAI API key for Whisper transcription")
    langsmith_api_key: str | None = Field(None, description="LangSmith tracing")

    # LLM Config
    model_name: str = Field("claude-sonnet-4-20250514", description="Claude model")
    temperature: float = Field(0.3, ge=0, le=1)
    max_tokens: int = Field(4096, ge=100, le=8192)

    # System Config
    log_level: str = Field("INFO", description="Logging level")
    environment: str = Field("development", description="dev/staging/production")

    # Budget Constraints
    max_budget_usd: float = Field(50000.0, description="Budget máximo absoluto")
    approval_threshold_usd: float = Field(10000.0, description="Requer aprovação")

    # Performance
    max_retries: int = Field(3, description="Max retries para tool calls")
    timeout_seconds: int = Field(30, description="Timeout padrão")

    # Enuygun MCP (hotel search upstream)
    enuygun_mcp_url: str = Field(
        "https://mcp.enuygun.com/mcp", description="Enuygun upstream MCP endpoint"
    )
    enuygun_oauth_client_id: str | None = Field(None, description="Enuygun OAuth client ID")
    enuygun_oauth_client_secret: str | None = Field(None, description="Enuygun OAuth secret")
    enuygun_oauth_token_url: str | None = Field(None, description="Enuygun OAuth token URL")
    enuygun_oauth_scope: str | None = Field(None, description="Enuygun OAuth scope")

    # Storage
    redis_url: str = Field("redis://localhost:6379/0", description="Redis connection")
    postgres_url: str | None = Field(None, description="PostgreSQL connection")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached singleton Settings instance.

    Creates the instance on first call, reading from .env and
    environment variables. Subsequent calls return the same object.
    """
    global _settings  # noqa: PLW0603
    if _settings is None:
        _settings = Settings()
    return _settings
