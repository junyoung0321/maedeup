import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import issue_jwt
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
    "https://www.googleapis.com/auth/calendar.events",
])


@router.get("/google")
async def google_login():
    if not settings.GOOGLE_CLIENT_ID.strip():
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID is not configured.")
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",  # refresh_token을 항상 발급받기 위해
        "state": state,
    }
    response = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        max_age=600,
        samesite="lax",
        secure=settings.APP_ENV.lower() not in {"development", "dev"},
    )
    return response


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str = Query(...),
    oauth_state: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    if not oauth_state or not secrets.compare_digest(oauth_state, state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
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
            try:
                token_data = token_resp.json()
            except ValueError as exc:
                raise HTTPException(status_code=502, detail="Google token response was not valid JSON.") from exc
            if token_resp.status_code != 200:
                error_detail = token_data.get("error_description") or token_data.get("error") or "Google token exchange failed"
                raise HTTPException(status_code=401, detail=error_detail)
            access_token = token_data.get("access_token")
            if not isinstance(access_token, str) or not access_token.strip():
                raise HTTPException(status_code=400, detail="Missing access token in OAuth response")

            userinfo_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            try:
                userinfo = userinfo_resp.json()
            except ValueError as exc:
                raise HTTPException(status_code=502, detail="Google userinfo response was not valid JSON.") from exc
            if userinfo_resp.status_code != 200:
                error_detail = userinfo.get("error_description") or userinfo.get("error") or "Google userinfo request failed"
                raise HTTPException(status_code=401, detail=error_detail)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Google OAuth request timed out.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google OAuth request failed.") from exc

    email = userinfo.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Missing email in Google user info")
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if user is None:
        user = User(
            email=email,
            name=userinfo.get("name", email),
            picture=userinfo.get("picture"),
            google_access_token=access_token,
            google_refresh_token=token_data.get("refresh_token"),
        )
        session.add(user)
    else:
        # 액세스 토큰은 항상 갱신, 리프레시 토큰은 새로 발급된 경우에만 갱신
        user.google_access_token = access_token
        if token_data.get("refresh_token"):
            user.google_refresh_token = token_data.get("refresh_token")

    await session.commit()
    await session.refresh(user)

    token = issue_jwt(
        user_id=user.id,
        email=user.email,
        name=user.name,
        picture=user.picture,
        calendar_consent=user.calendar_consent,
    )
    response = RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={token}")
    response.delete_cookie("oauth_state")
    return response
