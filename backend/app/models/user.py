from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column, Text, text
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    name: str = Field(max_length=128)
    picture: Optional[str] = Field(default=None)
    home_base: Optional[str] = Field(default=None, max_length=128)
    food_preferences: Optional[list[str]] = Field(default=None, sa_column=Column(JSON(), nullable=True))
    food_preference_note: Optional[str] = Field(default=None, max_length=255)

    # Personal data extension. AI가 모임 종료 시 chat에서 추출, 또는 사용자가
    # /settings에서 직접 입력. 둘 다 같은 칼럼에 저장됨.
    food_restrictions: Optional[list[str]] = Field(default=None, sa_column=Column(JSON(), nullable=True))
    liked_areas: Optional[list[str]] = Field(default=None, sa_column=Column(JSON(), nullable=True))
    disliked_areas: Optional[list[str]] = Field(default=None, sa_column=Column(JSON(), nullable=True))
    time_preference: Optional[str] = Field(default=None, max_length=255)
    transport_mode: Optional[str] = Field(default=None, max_length=32)
    # category_name(str) → AI가 채웠는지 여부(bool). 사용자 수동 수정 시 False.
    # 홈 PersonalData UI의 ✨ 마크 결정에 사용.
    is_ai_filled: dict[str, bool] = Field(
        default_factory=dict,
        sa_column=Column(JSON(), nullable=False, server_default=text("'{}'::json")),
    )

    google_access_token: Optional[str] = Field(default=None, sa_column=Column(Text(), nullable=True))
    google_refresh_token: Optional[str] = Field(default=None, sa_column=Column(Text(), nullable=True))
    calendar_consent: bool = Field(default=False, index=True)

    # QuickPreferences 카테고리별 공유 토글. 사용자가 OFF하면 해당 카테고리 데이터는
    # group recommendation 합성(_get_room_member_constraints)에서 제외됨.
    # 기본 True — opt-out 모델.
    share_food_data: bool = Field(default=True)
    share_location_data: bool = Field(default=True)
    share_schedule_data: bool = Field(default=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
