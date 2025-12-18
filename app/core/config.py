"""Application configuration from environment variables."""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App Configuration
    APP_NAME: str = "rag-profile-agent"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_VERSION: str = "v1"
    
    # FastAPI
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", "8000"))  # Railway sets PORT env var
    WORKERS: int = 4
    
    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "profile_agent"
    POSTGRES_USER: str = "profile_user"
    POSTGRES_PASSWORD: str = "secure_password_123"
    DATABASE_URL: Optional[str] = None
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None
    
    def get_database_url(self) -> str:
        """Get or construct database URL from components."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    def get_redis_url(self) -> str:
        """Get or construct Redis URL from components."""
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # Celery (defaults, can be overridden by .env or docker-compose)
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"  # Fastest model for quick responses
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    MAX_TOKENS: int = 300  # Reduced for faster generation and more concise responses
    TEMPERATURE: float = 0.7
    ENABLE_GROUNDING: bool = True  # Set to False to disable grounding verification for faster responses
    
    # LangSmith
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "rag-profile-agent"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    
    # AWS S3
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET: str = "profile-documents2"
    S3_REGION: str = "us-east-1"
    
    # Security
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Vector Search
    VECTOR_DIMENSION: int = 1536
    TOP_K_RESULTS: int = 3  # Reduced to 3 for faster retrieval and smaller context (only use top 2 in LLM)
    SIMILARITY_THRESHOLD: float = 0.15  # Lowered to 0.15 to catch more relevant matches (0.3 was too strict, caused 0 results)
    
    # Modular RAG Settings
    ENABLE_HYBRID_RETRIEVAL: bool = True  # Enable hybrid retrieval (dense + sparse)
    ENABLE_RERANKING: bool = True  # Enable cross-encoder reranking
    ENABLE_QUERY_ROUTING: bool = True  # Enable query routing and rewriting
    ENABLE_MULTI_HOP: bool = False  # Enable multi-hop iterative retrieval (slower but better for complex queries)
    ENABLE_HYDE: bool = False  # Enable HyDE (Hypothetical Document Embeddings)
    ENABLE_ANSWER_VALIDATION: bool = True  # Enable answer validation and correction
    RERANK_TOP_K: int = 10  # Number of documents to rerank
    DENSE_RETRIEVAL_TOP_K: int = 20  # Top-k for dense retrieval in hybrid
    SPARSE_RETRIEVAL_TOP_K: int = 20  # Top-k for sparse retrieval in hybrid
    MULTI_HOP_MAX_HOPS: int = 3  # Maximum iterations for multi-hop retrieval
    
    # Celery Schedule
    DOCUMENT_SYNC_SCHEDULE: str = "*/15 * * * *"
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env


settings = Settings()

