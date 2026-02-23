from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://study_assistant:study_assistant@localhost:5432/study_assistant"

    # Gemini AI
    gemini_api_key: str = ""

    # Models
    embedding_model: str = "text-embedding-004"
    generation_model: str = "gemini-2.5-flash-lite"

    # Embedding dimensions (gemini-embedding-001 with output_dimensionality=768)
    embedding_dimensions: int = 768

    # Chunking
    chunk_size: int = 700
    chunk_overlap: int = 100

    # File uploads
    upload_dir: Path = Path("./uploads")
    max_upload_size_mb: int = 50

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 72

    # Frontend URL (for OAuth redirect)
    frontend_url: str = "http://localhost:5173"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic (replaces asyncpg with psycopg2)."""
        return self.database_url.replace("+asyncpg", "")


settings = Settings()
