"""Application configuration settings."""

from functools import lru_cache
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "OmniSift"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://omnisift:omnisift_password@localhost:5432/omnisift"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600

    # Object Storage (SeaweedFS S3 API)
    s3_endpoint_url: str = "http://localhost:8333"
    s3_access_key: str = "omnisiftadmin"
    s3_secret_key: str = "omnisiftsecret"
    s3_region: str = "us-east-1"
    s3_bucket_documents: str = "documents"
    s3_bucket_processed: str = "processed"
    s3_bucket_embeddings: str = "embeddings"

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # Processing
    max_file_size_mb: int = 100
    allowed_file_types: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
    ]

    # Embeddings
    embedding_provider: str = "gemini"  # gemini, openai, local
    embedding_model: str = "gemini-embedding-2"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 32
    gemini_api_key: str = ""
    gemini_output_dimensionality: int = 1536

    # Re-ranking (Cross-Encoder)
    reranker_provider: str = "local"  # cohere, local, onnx
    reranker_model: str = "BAAI/bge-reranker-base"  # Model for local/onnx
    reranker_top_k: int = 5  # Final number of parent chunks after re-ranking
    cohere_api_key: str = ""  # For Cohere Rerank API
    reranker_model_path: str = ""  # Path to ONNX model file
    reranker_tokenizer: str = ""  # Tokenizer for ONNX model
    onnx_provider: str = "CPUExecutionProvider"  # CPUExecutionProvider, CUDAExecutionProvider

    # Confidence Floor
    relevance_score_threshold: float = 0.25  # Minimum cross-encoder score for sufficient context

    # Vector Search
    vector_similarity_threshold: float = 0.7
    vector_max_results: int = 10

    # LLM (Generation)
    llm_model: str = "gemini/gemini-3.8-flash"  # LiteLLM format: provider/model
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    llm_top_p: float = 1.0
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()