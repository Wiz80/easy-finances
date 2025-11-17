"""
Application configuration management using Pydantic Settings.
All settings are loaded from environment variables.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Database Configuration
    # =========================================================================
    postgres_user: str = Field(default="finanzas_user")
    postgres_password: str = Field(default="finanzas_password")
    postgres_db: str = Field(default="finanzas_db")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # =========================================================================
    # LLM Provider Configuration
    # =========================================================================
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    google_api_key: str = Field(default="")
    llm_provider: Literal["openai", "anthropic", "google"] = Field(default="openai")

    # =========================================================================
    # LlamaParse Configuration
    # =========================================================================
    llamaparse_api_key: str = Field(default="")

    # =========================================================================
    # Audio Processing Configuration
    # =========================================================================
    whisper_provider: Literal["api", "local"] = Field(default="api")
    whisper_model: str = Field(default="whisper-1")

    # =========================================================================
    # Object Storage (MinIO) Configuration
    # =========================================================================
    minio_host: str = Field(default="localhost")
    minio_port: int = Field(default=9000)
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket_name: str = Field(default="finanzas-receipts")
    minio_secure: bool = Field(default=False)

    # =========================================================================
    # Logging Configuration
    # =========================================================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_format: Literal["json", "console"] = Field(default="json")

    # =========================================================================
    # LangChain Tracing (LangSmith)
    # =========================================================================
    langchain_tracing_v2: bool = Field(default=False)
    langchain_api_key: str = Field(default="")
    langchain_project: str = Field(default="finanzas-mvp")

    # =========================================================================
    # Prompt Management (Langfuse - Future)
    # =========================================================================
    prompt_source: Literal["local", "langfuse"] = Field(default="local")
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")

    # =========================================================================
    # Qdrant Vector Database Configuration
    # =========================================================================
    qdrant_host: str = Field(default="localhost")
    qdrant_http_port: int = Field(default=6333)
    qdrant_grpc_port: int = Field(default=6334)

    @property
    def qdrant_url(self) -> str:
        """Construct Qdrant HTTP URL."""
        return f"http://{self.qdrant_host}:{self.qdrant_http_port}"

    # =========================================================================
    # Application Settings
    # =========================================================================
    environment: Literal["development", "staging", "production"] = Field(
        default="development"
    )
    secret_key: str = Field(default="development-secret-key-change-in-production")
    confidence_threshold: float = Field(default=0.7)

    # =========================================================================
    # n8n Configuration (for reference, used by docker-compose)
    # =========================================================================
    n8n_host: str = Field(default="localhost")
    n8n_port: int = Field(default=5678)


# Global settings instance
settings = Settings()

