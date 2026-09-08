from datetime import timedelta
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, status, Depends
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.api.deps import get_current_admin

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    if payload.username != settings.ADMIN_USERNAME or not verify_password(payload.password, settings.ADMIN_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de administrador incorrectas"
        )
    
    token = create_access_token(
        subject=payload.username,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return TokenResponse(access_token=token, username=payload.username)

@router.get("/me")
def get_current_user_profile(current_admin: str = Depends(get_current_admin)):
    return {
        "authenticated": True,
        "username": current_admin,
        "role": "admin"
    }

