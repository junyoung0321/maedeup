from typing import Any

import httpx

from app.core.config import settings

KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def _get_kakao_api_key() -> str:
    return settings.KAKAO_API_KEY or settings.KAKAO_REST_API_KEY


async def search_address(keyword: str) -> dict[str, str] | None:
    api_key = _get_kakao_api_key()
    if not api_key or not keyword.strip():
        return None

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                KAKAO_ADDRESS_URL,
                params={"query": keyword.strip()},
                headers={"Authorization": f"KakaoAK {api_key}"},
                timeout=5.0,
            )
    except Exception:
        return None

    if resp.status_code != 200:
        return None

    documents = resp.json().get("documents", [])
    if not documents:
        return None

    first = documents[0]
    address = first.get("address") or {}
    return {
        "x": str(address.get("x") or first.get("x") or ""),
        "y": str(address.get("y") or first.get("y") or ""),
        "address_name": str(address.get("address_name") or first.get("address_name") or ""),
    }


async def search_keyword(
    query: str,
    *,
    x: str | None = None,
    y: str | None = None,
    radius: int | None = None,
    size: int = 10,
) -> list[dict[str, Any]]:
    api_key = _get_kakao_api_key()
    if not api_key or not query.strip():
        return []

    params: dict[str, Any] = {"query": query.strip(), "size": size}
    if x and y:
        params["x"] = x
        params["y"] = y
        if radius is not None:
            params["radius"] = radius

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                KAKAO_KEYWORD_URL,
                params=params,
                headers={"Authorization": f"KakaoAK {api_key}"},
                timeout=5.0,
            )
    except Exception:
        return []

    if resp.status_code != 200:
        return []

    return list(resp.json().get("documents", []))
