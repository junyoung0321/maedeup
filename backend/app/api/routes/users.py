from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import _issue_jwt
from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


class ConsentUpdate(BaseModel):
    calendar_consent: bool


class ConsentResponse(BaseModel):
    token: str
    calendar_consent: bool


@router.patch("/me/consent", response_model=ConsentResponse)
async def update_consent(
    body: ConsentUpdate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    캘린더 수집 동의 여부를 업데이트하고 갱신된 JWT를 반환합니다.
    """
    user = await session.get(User, int(current_user.sub))
    user.calendar_consent = body.calendar_consent
    session.add(user)
    await session.commit()
    await session.refresh(user)

    new_token = _issue_jwt(user)
    return ConsentResponse(token=new_token, calendar_consent=user.calendar_consent)
