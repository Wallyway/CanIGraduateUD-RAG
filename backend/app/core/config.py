from typing import List, Union
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "CanIGraduateUD-RAG"
    API_V1_STR: str = "/api/v1"

    # LLM Settings
    LLM_PROVIDER: str = "openrouter"  # openrouter, openai, gemini
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Embeddings Settings
    EMBEDDING_PROVIDER: str = "openrouter" # openrouter, openai, chromadb-default
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Admin Credentials & Security
    ADMIN_USERNAME: str = "admin_ud"
    ADMIN_PASSWORD: str = "graduacion_sistemas_2026!"
    JWT_SECRET_KEY: str = "can-i-graduate-ud-secret-key-change-in-production-random-hash-9823479234"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Inbound Webhook Secret for Power Automate / Email Relay
    WEBHOOK_SECRET_KEY: str = "ud-incoming-email-webhook-secret-token-12345"


    # Storage Paths
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    CHROMA_PERSIST_DIRECTORY: str = ""
    DATABASE_URL: str = ""

    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        import json
        try:
            return json.loads(v)
        except Exception:
            return ["http://localhost:3000", "http://127.0.0.1:3000"]

    def __init__(self, **values):
        super().__init__(**values)
        if not self.CHROMA_PERSIST_DIRECTORY:
            self.CHROMA_PERSIST_DIRECTORY = os.path.join(self.DATA_DIR, "chroma")
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{os.path.join(self.DATA_DIR, 'database.sqlite')}"
        
        # Ensure directories exist
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.CHROMA_PERSIST_DIRECTORY, exist_ok=True)
        os.makedirs(os.path.join(self.DATA_DIR, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(self.DATA_DIR, "seed_documents"), exist_ok=True)

settings = Settings()

