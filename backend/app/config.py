from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+psycopg2://study_assistant:study_assistant@localhost:5432/study_assistant"

    # GCP
    gcp_project_id: str = ""
    gcp_location: str = "us-central1"
    gcs_bucket_name: str = ""
    # Service account key JSON string (for production only).
    # In development, leave empty to use ADC (gcloud auth application-default login).
    gcp_service_account_json: str = ""

    # Models
    embedding_model: str = "gemini-embedding-001"
    generation_model: str = "gemini-2.5-flash-lite"
    multimodal_embedding_model: str = "multimodalembedding@001"

    # Embedding dimensions
    embedding_dimensions: int = 768  # gemini-embedding-001
    image_embedding_dimensions: int = 1408  # multimodalembedding@001

    # Chunking
    chunk_size: int = 700
    chunk_overlap: int = 100

    # File uploads
    max_upload_size_mb: int = 50

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 72

    # Static files directory (set in production to serve frontend build)
    static_dir: str = ""

    # Environment
    environment: str = "development"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
