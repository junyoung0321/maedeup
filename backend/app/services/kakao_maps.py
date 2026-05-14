"""Kakao Local API 래퍼.

PR-V1.5 / F7 (2026-05-14): 장애 vs 정상 0건 narrator 구분을 위해
예외 분리. 5xx·timeout·네트워크 오류는 KakaoApiError로 raise.
404·400·정상 빈 응답은 그대로 [] / None 반환.

호출자(nodes/place.py)는 KakaoApiError를 catch해 narrator를 분기.
"""
from typing import Any

import httpx

from app.core.config import settings

KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoApiError(RuntimeError):
    """카카오맵 API 호출 실패 (5xx, timeout, 네트워크).

    PR-V1.5 / F7 — 정상 빈 응답(0건)과 구분.
    호출자가 narrator를 "장소 검색 서비스 일시 불가" 로 띄울 수 있게.
    """

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


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
    except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as exc:
        # PR-V1.5 / F7: 장애 — narrator 분기를 위해 raise.
        raise KakaoApiError(f"kakao search_address transport failed: {exc}", cause=exc) from exc
    except Exception:
        return None

    if resp.status_code >= 500:
        # PR-V1.5 / F7: 5xx도 장애로 분류.
        raise KakaoApiError(f"kakao search_address 5xx: {resp.status_code}")
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
    except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as exc:
        # PR-V1.5 / F7: 장애 — narrator 분기를 위해 raise.
        raise KakaoApiError(f"kakao search_keyword transport failed: {exc}", cause=exc) from exc
    except Exception:
        return []

    if resp.status_code >= 500:
        # PR-V1.5 / F7: 5xx도 장애로 분류.
        raise KakaoApiError(f"kakao search_keyword 5xx: {resp.status_code}")
    if resp.status_code != 200:
        return []

    return list(resp.json().get("documents", []))
