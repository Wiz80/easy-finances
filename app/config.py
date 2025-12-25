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
    # Object Storage (MinIO)
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
    qdrant_api_key: str | None = Field(default=None)

    @property
    def qdrant_url(self) -> str:
        """Construct Qdrant HTTP URL."""
        return f"http://{self.qdrant_host}:{self.qdrant_http_port}"

    # =========================================================================
    # Vanna AI Configuration
    # =========================================================================
    # Collection names
    vanna_ddl_collection: str = Field(default="vanna_ddl")
    vanna_doc_collection: str = Field(default="vanna_documentation")
    vanna_sql_collection: str = Field(default="vanna_sql")

    # Read-only database user for Vanna queries
    vanna_db_user: str = Field(default="vanna_reader")
    vanna_db_password: str = Field(default="vanna_readonly_password")

    # Query execution limits
    vanna_query_timeout_seconds: int = Field(default=30)
    vanna_max_result_rows: int = Field(default=1000)

    # Training configuration
    vanna_training_llm_provider: Literal["openai", "anthropic"] = Field(default="openai")
    vanna_embedding_model: str = Field(default="text-embedding-3-small")
    vanna_vector_dimension: int = Field(default=1536)

    @property
    def vanna_database_url(self) -> str:
        """Construct read-only PostgreSQL connection URL for Vanna."""
        return (
            f"postgresql://{self.vanna_db_user}:{self.vanna_db_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

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

    # =========================================================================
    # Twilio WhatsApp Configuration
    # =========================================================================
    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_whatsapp_from: str = Field(
        default="whatsapp:+14155238886"
    )  # Sandbox number
    
    # Webhook Configuration
    webhook_base_url: str = Field(default="")  # e.g., https://abc123.ngrok.io
    twilio_webhook_path: str = Field(default="/api/v1/webhook/twilio")
    
    @property
    def twilio_webhook_url(self) -> str:
        """Full Twilio webhook URL."""
        return f"{self.webhook_base_url}{self.twilio_webhook_path}"

    # =========================================================================
    # Conversation Settings
    # =========================================================================
    conversation_timeout_minutes: int = Field(default=30)
    max_conversation_messages: int = Field(default=100)

    # =========================================================================
    # Azure Blob Storage (Conversation Cache)
    # =========================================================================
    azure_storage_connection_string: str = Field(default="")
    azure_storage_account_name: str = Field(default="")
    azure_storage_account_key: str = Field(default="")
    azure_conversation_container: str = Field(default="conversation-cache")
    azure_conversation_ttl_hours: int = Field(default=24)  # TTL for cached conversations

    @property
    def azure_storage_configured(self) -> bool:
        """Check if Azure Storage is configured."""
        return bool(self.azure_storage_connection_string or self.azure_storage_account_name)


# Global settings instance
settings = Settings()

