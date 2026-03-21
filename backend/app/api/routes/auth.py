from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_session
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.readonly",
])


@router.get("/google")
async def google_login():
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",  # refresh_token을 항상 발급받기 위해
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/google/callback")
async def google_callback(code: str, session: AsyncSession = Depends(get_session)):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_resp.json()

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        userinfo = userinfo_resp.json()

    email = userinfo["email"]
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if user is None:
        user = User(
            email=email,
            name=userinfo.get("name", email),
            picture=userinfo.get("picture"),
            google_access_token=token_data.get("access_token"),
            google_refresh_token=token_data.get("refresh_token"),
        )
        session.add(user)
    else:
        # 액세스 토큰은 항상 갱신, 리프레시 토큰은 새로 발급된 경우에만 갱신
        user.google_access_token = token_data.get("access_token")
        if token_data.get("refresh_token"):
            user.google_refresh_token = token_data.get("refresh_token")

    await session.commit()
    await session.refresh(user)

    token = _issue_jwt(user)
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={token}")


def _issue_jwt(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "calendar_consent": user.calendar_consent,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
