"""
Auth routes: login (username/password -> JWT).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> dict:
    """
    Exchange username and password for a JWT.
    Demo: use AUTH_DEMO_USERNAME and AUTH_DEMO_PASSWORD (or defaults).
    """
    if body.username != settings.auth_demo_username or body.password != settings.auth_demo_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(sub=body.username)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(user: CurrentUser) -> dict:
    """
    Returns the currently authenticated user. Use to verify JWT.
    """
    return {"authenticated": True, "username": user}
