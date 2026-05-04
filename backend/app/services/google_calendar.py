from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Iterable

import httpx
from fastapi import HTTPException
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.meeting import MeetingSchedule
from app.models.user import User

logger = logging.getLogger(__name__)

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


def _user_can_receive_calendar_event(user: User) -> bool:
    if user.is_guest:
        return False
    if not user.calendar_consent:
        return False
    if not (user.google_access_token or user.google_refresh_token):
        return False
    return True


async def update_calendar_event(
    user: User,
    session: AsyncSession,
    event_id: str,
    title: str,
    start_datetime: datetime,
    end_datetime: datetime,
    location: str | None = None,
) -> dict[str, Any] | None:
    """Update an existing event in `user`'s primary calendar via PATCH."""
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
    url = f"{GOOGLE_EVENTS_URL}/{event_id}"
    access_token = await get_google_access_token(user, session)
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.patch(url, json=event_body, headers=headers)
            if response.status_code == 401:
                refreshed_token = await get_google_access_token(user, session, force_refresh=True)
                response = await client.patch(
                    url,
                    json=event_body,
                    headers={"Authorization": f"Bearer {refreshed_token}"},
                )
    except httpx.HTTPError as exc:
        raise GoogleCalendarError("Google Calendar request failed") from exc

    if response.status_code == 401:
        raise GoogleCalendarAuthError()
    if response.status_code == 404:
        # Event was deleted on Google's side. Caller may want to recreate.
        raise GoogleCalendarError(f"Calendar event {event_id} not found")
    if response.status_code not in (200, 201):
        raise GoogleCalendarError(
            f"Google Calendar event update failed with status {response.status_code}"
        )
    return response.json()


async def delete_calendar_event(
    user: User,
    session: AsyncSession,
    event_id: str,
) -> bool:
    """Delete an event from `user`'s primary calendar via DELETE.

    Returns True if Google reports the event removed (or it was already gone —
    404/410 is treated as success). Raises on auth or other transport errors.
    """
    url = f"{GOOGLE_EVENTS_URL}/{event_id}"
    access_token = await get_google_access_token(user, session)
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.delete(url, headers=headers)
            if response.status_code == 401:
                refreshed_token = await get_google_access_token(user, session, force_refresh=True)
                response = await client.delete(
                    url,
                    headers={"Authorization": f"Bearer {refreshed_token}"},
                )
    except httpx.HTTPError as exc:
        raise GoogleCalendarError("Google Calendar request failed") from exc

    if response.status_code == 401:
        raise GoogleCalendarAuthError()
    # 200/204 = deleted; 404/410 = already gone — both count as success.
    if response.status_code in (200, 204, 404, 410):
        return True
    raise GoogleCalendarError(
        f"Google Calendar event deletion failed with status {response.status_code}"
    )


async def delete_events_for_meeting_members(
    meeting: MeetingSchedule,
    members: Iterable[User],
    session: AsyncSession,
) -> dict[str, str]:
    """Delete every member's Google Calendar event for this meeting.

    Best-effort: per-member failures are logged. All entries are dropped from
    the returned mapping regardless of outcome — orphan events on a member's
    calendar are an accepted edge case (re-deleting on a soft-cancelled meeting
    has no UI path anyway).

    Returns the residual mapping (typically empty; only entries whose member
    isn't in `members` survive).
    """
    remaining = dict(meeting.google_event_ids or {})
    members_by_id = {m.id: m for m in members}

    for user_id_str, event_id in list(remaining.items()):
        try:
            user_id = int(user_id_str)
        except ValueError:
            del remaining[user_id_str]
            continue
        member = members_by_id.get(user_id)
        if member is None or member.is_guest:
            del remaining[user_id_str]
            continue
        try:
            await delete_calendar_event(member, session, event_id)
        except GoogleCalendarAuthError:
            logger.info(
                "Calendar deletion skipped for user_id=%s meeting_id=%s — auth expired",
                user_id, meeting.id,
            )
        except (GoogleCalendarError, Exception):
            logger.warning(
                "Failed to delete Google Calendar event for user_id=%s meeting_id=%s",
                user_id, meeting.id, exc_info=True,
            )
        del remaining[user_id_str]

    return remaining


async def sync_events_for_meeting_members(
    meeting: MeetingSchedule,
    members: Iterable[User],
    session: AsyncSession,
) -> dict[str, str]:
    """Create-or-update a Google Calendar event for each eligible member.

    For each consenting member:
      - If `meeting.google_event_ids[user_id]` exists → PATCH that event
      - Else → POST a new event

    Best-effort: per-member failures are logged and skipped, never raised.

    Returns the FULL updated mapping (user_id-as-str → event_id), including
    pre-existing entries that were just updated. Caller assigns the result
    back to `meeting.google_event_ids` and commits.
    """
    updated = dict(meeting.google_event_ids or {})
    end_dt = meeting.end_at or (meeting.scheduled_at + timedelta(hours=1))

    for member in members:
        key = str(member.id)
        if not _user_can_receive_calendar_event(member):
            continue
        try:
            if key in updated:
                await update_calendar_event(
                    member,
                    session,
                    event_id=updated[key],
                    title=meeting.title,
                    start_datetime=meeting.scheduled_at,
                    end_datetime=end_dt,
                    location=meeting.location_name,
                )
            else:
                response = await create_calendar_event(
                    member,
                    session,
                    title=meeting.title,
                    start_datetime=meeting.scheduled_at,
                    end_datetime=end_dt,
                    location=meeting.location_name,
                )
                event_id = (response or {}).get("id")
                if event_id:
                    updated[key] = event_id
        except GoogleCalendarAuthError:
            logger.info(
                "Skipping Google Calendar sync for user_id=%s meeting_id=%s — auth expired",
                member.id, meeting.id,
            )
            continue
        except (GoogleCalendarError, Exception):
            logger.warning(
                "Failed to sync Google Calendar event for user_id=%s meeting_id=%s",
                member.id, meeting.id, exc_info=True,
            )
            continue

    return updated
