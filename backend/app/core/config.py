import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    PROJECT_NAME: str = "Industrial Product Truth Engine"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # AI Provider
    AI_PROVIDER: str = "ollama"  # 'ollama' or 'openrouter'
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_VISION_MODEL: str = "qwen2-vl:7b"
    EMBEDDING_MODEL: str = "nomic-embed-text"

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: Optional[str] = "qwen/qwen-2.5-72b-instruct"

    # PostgreSQL
    POSTGRES_URL: str = "postgresql://ipte:iptepass@localhost:5432/ipte_db"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "iptepassword"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

settings = Settings()
