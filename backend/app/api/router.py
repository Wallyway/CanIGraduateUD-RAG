from fastapi import APIRouter
from app.api.v1 import chat, admin, documents, webhooks, auth

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat Estudiantes"])
api_router.include_router(admin.router, prefix="/admin", tags=["Administración"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documentos Normativos"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks M365"])

