from typing import List, Union, Any
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
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_FALLBACK_MODELS: Union[List[str], str] = [
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001"
    ]
    OPENROUTER_TIMEOUT: float = 30.0
    OPENROUTER_MAX_RETRIES: int = 3
    OPENROUTER_BACKOFF_FACTOR: float = 1.5

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

    # SMTP / Feedback Email Delivery
    FEEDBACK_TARGET_EMAIL: str = "canigraduateud@gmail.com"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_TLS: bool = True


    # Redis / Upstash Cache Settings
    REDIS_URL: str = ""
    UPSTASH_REDIS_URL: str = ""

    # Storage Paths
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    CHROMA_PERSIST_DIRECTORY: str = ""
    DATABASE_URL: str = ""

    # Database Pool Settings (High Concurrency > 200 users)
    DB_POOL_SIZE: int = 30
    DB_MAX_OVERFLOW: int = 50
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_PRE_PING: bool = True

    # Server Concurrency & Streaming Settings (>200 concurrent students)
    STREAM_CONCURRENCY_LIMIT: int = 150
    SSE_KEEPALIVE_INTERVAL_SECONDS: float = 15.0
    QUEUE_MAX_WAIT_SECONDS: float = 15.0
    QUEUE_CAPACITY: int = 100

    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://canigraduateud.site",
        "https://www.canigraduateud.site",
    ]

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

    @field_validator("OPENROUTER_FALLBACK_MODELS", mode="before")
    @classmethod
    def assemble_fallback_models(cls, v: Any) -> List[str]:
        if v is None:
            return ["meta-llama/llama-3.3-70b-instruct", "google/gemini-2.0-flash-001"]
        if isinstance(v, str):
            v_str = v.strip()
            if not v_str:
                return []
            if v_str.startswith("["):
                import json
                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(i).strip().strip("'\"") for i in parsed if str(i).strip().strip("'\"")]
                except Exception:
                    pass
                import ast
                try:
                    parsed = ast.literal_eval(v_str)
                    if isinstance(parsed, list):
                        return [str(i).strip().strip("'\"") for i in parsed if str(i).strip().strip("'\"")]
                except Exception:
                    pass
            cleaned = v_str.strip("[]")
            items = []
            for item in cleaned.split(","):
                clean_item = item.strip().strip("'\"")
                if clean_item:
                    items.append(clean_item)
            return items
        elif isinstance(v, (list, tuple, set)):
            return [str(i).strip().strip("'\"") for i in v if str(i).strip().strip("'\"")]
        return ["meta-llama/llama-3.3-70b-instruct", "google/gemini-2.0-flash-001"]

    def __init__(self, **values):
        super().__init__(**values)
        if not self.CHROMA_PERSIST_DIRECTORY:
            self.CHROMA_PERSIST_DIRECTORY = os.path.join(self.DATA_DIR, "chroma")
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{os.path.join(self.DATA_DIR, 'database.sqlite')}"
        elif self.DATABASE_URL.strip().lower().startswith("postgres://"):
            # Normalize legacy postgres:// scheme to postgresql://
            clean_url = self.DATABASE_URL.strip()
            self.DATABASE_URL = "postgresql://" + clean_url[11:]
        
        if not os.path.isabs(self.DATA_DIR):
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            candidate = os.path.join(backend_dir, self.DATA_DIR)
            if os.path.exists(candidate):
                self.DATA_DIR = candidate
            else:
                self.DATA_DIR = os.path.abspath(self.DATA_DIR)

        # Ensure directories exist
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.CHROMA_PERSIST_DIRECTORY, exist_ok=True)
        os.makedirs(os.path.join(self.DATA_DIR, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(self.DATA_DIR, "seed_documents"), exist_ok=True)

settings = Settings()

