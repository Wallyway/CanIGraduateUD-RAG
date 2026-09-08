import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import init_db
from app.api.router import api_router
from app.scripts.seed_db import seed_knowledge_base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database tables & seed initial documents if empty
    logger.info("Starting CanIGraduateUD-RAG backend...")
    init_db()
    try:
        seed_knowledge_base()
    except Exception as e:
        logger.warning(f"Seed knowledge base notice: {e}")

    yield

    # Shutdown
    logger.info("Shutting down CanIGraduateUD-RAG backend.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
    description="Sistema RAG oficial para resolver dudas sobre graduación en Ingeniería de Sistemas - Universidad Distrital Francisco José de Caldas"
)

# Configure CORS
origins = settings.BACKEND_CORS_ORIGINS if isinstance(settings.BACKEND_CORS_ORIGINS, list) else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in origins else origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck
@app.get("/api/v1/health", tags=["Estado"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "llm_provider": settings.LLM_PROVIDER
    }

app.include_router(api_router, prefix=settings.API_V1_STR)

