from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_DATA_DIR = str(Path(__file__).resolve().parents[3] / "data")
if _DATA_DIR not in sys.path:
    sys.path.insert(0, _DATA_DIR)

from serving.quick_recommend import quick_recommend  # noqa: E402


async def ml_place_search(
    location: str | None,
    meeting_type: str,
    headcount: int,
    top_k: int = 5,
) -> list[dict]:
    result = await asyncio.to_thread(
        quick_recommend,
        location=location,
        meeting_type=meeting_type,
        headcount=headcount,
        top_k=top_k,
    )
    places = []
    for item in result.get("recommendations", []):
        places.append({
            "place_id": str(item.get("naver_place_id", "")),
            "name": item.get("place_name", ""),
            "score": float(item.get("score", 0.0)),
            "distance_label": item.get("distance_label", ""),
            "reasons": item.get("reasons", []),
            "image_url": item.get("image_url"),
            "address": "",
            "category": "",
        })
    return places
