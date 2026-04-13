from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


async def create_calendar_event(
    token: str,
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
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_EVENTS_URL,
                json=event_body,
                headers=headers,
            )
    except Exception:
        return None

    if response.status_code not in (200, 201):
        return None
    return response.json()
