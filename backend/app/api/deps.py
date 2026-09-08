from typing import Optional
from fastapi import Depends, HTTPException, status, Header, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

def get_current_admin(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> str:
    """Validates JWT access token for admin endpoints."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó token de autenticación",
            headers={"WWW-Authenticate": "Bearer"}
        )
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return payload["sub"]

def verify_webhook_token(
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    secret: Optional[str] = Query(None)
) -> bool:
    """Verifies incoming webhook secret for Power Automate / external forwarders."""
    provided_secret = x_webhook_secret or secret
    if not provided_secret or provided_secret != settings.WEBHOOK_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token secreto de webhook inválido o ausente"
        )
    return True

