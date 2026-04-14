from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

bearer_scheme = HTTPBearer()


@dataclass
class AuthUser:
    sub: str
    email: str
    name: str
    picture: Optional[str]
    calendar_consent: bool = False


def issue_jwt(
    *,
    user_id: int,
    email: str,
    name: str,
    picture: Optional[str],
    calendar_consent: bool,
) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "picture": picture,
        "calendar_consent": calendar_consent,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict:
    """JWT를 검증하고 payload를 반환합니다. 실패 시 HTTPException 발생."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AuthUser:
    """HTTP 라우트용 인증 의존성. Authorization: Bearer <token> 헤더를 검증합니다."""
    payload = verify_token(credentials.credentials)
    return AuthUser(
        sub=payload["sub"],
        email=payload["email"],
        name=payload["name"],
        picture=payload.get("picture"),
        calendar_consent=payload.get("calendar_consent", False),
    )
