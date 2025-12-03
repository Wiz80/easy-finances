"""
Configuration for the Finanzas MCP Server.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MCP Server configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Database Configuration
    # =========================================================================
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_user: str = Field(default="finanzas_user")
    postgres_password: str = Field(default="finanzas_password")
    postgres_db: str = Field(default="finanzas_db")

    # Read-only user for Vanna queries
    vanna_db_user: str = Field(default="vanna_reader")
    vanna_db_password: str = Field(default="vanna_readonly_password")

    @property
    def database_url(self) -> str:
        """Main PostgreSQL connection URL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def vanna_database_url(self) -> str:
        """Read-only PostgreSQL connection URL for Vanna."""
        return (
            f"postgresql://{self.vanna_db_user}:{self.vanna_db_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # =========================================================================
    # LLM Configuration
    # =========================================================================
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o")

    # =========================================================================
    # Qdrant Configuration (for context storage)
    # =========================================================================
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_api_key: str | None = Field(default=None)

    # Collection names
    qdrant_ddl_collection: str = Field(default="vanna_ddl")
    qdrant_doc_collection: str = Field(default="vanna_documentation")
    qdrant_sql_collection: str = Field(default="vanna_sql")

    @property
    def qdrant_url(self) -> str:
        """Qdrant HTTP URL."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    # =========================================================================
    # Query Execution Limits
    # =========================================================================
    sql_query_timeout_seconds: int = Field(default=30)
    sql_max_result_rows: int = Field(default=1000)

    # =========================================================================
    # Server Configuration
    # =========================================================================
    transport: Literal["stdio", "http"] = Field(default="stdio")
    http_host: str = Field(default="0.0.0.0")
    http_port: int = Field(default=8080)

    # =========================================================================
    # Logging
    # =========================================================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")


# Global settings instance
settings = Settings()

