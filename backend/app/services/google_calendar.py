from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
from fastapi import HTTPException
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleCalendarError(Exception):
    pass


class GoogleCalendarAuthError(HTTPException, GoogleCalendarError):
    def __init__(
        self,
        detail: str = "Google Calendar authorization expired. Reconnect Google Calendar and try again.",
        ) -> None:
        HTTPException.__init__(self, status_code=401, detail=detail)


def _google_oauth_is_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID.strip() and settings.GOOGLE_CLIENT_SECRET.strip())


async def _refresh_google_access_token(user: User, session: AsyncSession) -> str:
    if not user.google_refresh_token:
        raise GoogleCalendarAuthError()
    if not _google_oauth_is_configured():
        raise HTTPException(
            status_code=500,
            detail="Google Calendar is not configured correctly. Missing OAuth client settings.",
        )

    credentials = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri=GOOGLE_TOKEN_URL,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    try:
        await asyncio.to_thread(credentials.refresh, Request())
    except RefreshError as exc:
        raise GoogleCalendarAuthError() from exc

    if not credentials.token:
        raise GoogleCalendarAuthError()

    user.google_access_token = credentials.token
    if credentials.refresh_token:
        user.google_refresh_token = credentials.refresh_token
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return credentials.token


async def get_google_access_token(
    user: User,
    session: AsyncSession,
    *,
    force_refresh: bool = False,
) -> str:
    if force_refresh:
        return await _refresh_google_access_token(user, session)

    if user.google_access_token:
        return user.google_access_token

    if user.google_refresh_token:
        return await _refresh_google_access_token(user, session)

    raise GoogleCalendarAuthError()


async def create_calendar_event(
    user: User,
    session: AsyncSession,
    title: str,
    start_datetime: datetime,
    end_datetime: datetime,
    location: str | None = None,
) -> dict[str, Any] | None:
    event_body = {
        "summary": title,
        "location": location or "",
        "start": {
            "dateTime": start_datetime.isoformat(),
            "timeZone": "Asia/Seoul",
        },
        "end": {
            "dateTime": end_datetime.isoformat(),
            "timeZone": "Asia/Seoul",
        },
    }
    access_token = await get_google_access_token(user, session)
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                GOOGLE_EVENTS_URL,
                json=event_body,
                headers=headers,
            )
            if response.status_code == 401:
                refreshed_token = await get_google_access_token(user, session, force_refresh=True)
                response = await client.post(
                    GOOGLE_EVENTS_URL,
                    json=event_body,
                    headers={"Authorization": f"Bearer {refreshed_token}"},
                )
    except httpx.HTTPError as exc:
        raise GoogleCalendarError("Google Calendar request failed") from exc

    if response.status_code == 401:
        raise GoogleCalendarAuthError()
    if response.status_code not in (200, 201):
        raise GoogleCalendarError(
            f"Google Calendar event creation failed with status {response.status_code}"
        )
    return response.json()
