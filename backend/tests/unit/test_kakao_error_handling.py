"""PR-V1.5 / F7 — 카카오맵 API 장애 vs 정상 0건 구분 검증.

`KakaoApiError`는 5xx·timeout·네트워크 오류에서 raise.
정상 빈 응답(0건)은 그대로 [] 반환.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.services import kakao_maps
from app.services.kakao_maps import KakaoApiError, search_address, search_keyword


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """httpx.AsyncClient 대체. behavior에 따라 응답/예외 결정."""

    def __init__(self, behavior: str, payload: dict | None = None):
        self._behavior = behavior
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        if self._behavior == "timeout":
            raise httpx.TimeoutException("timeout!")
        if self._behavior == "network":
            raise httpx.NetworkError("network down")
        if self._behavior == "5xx":
            return _FakeResponse(503)
        if self._behavior == "404":
            return _FakeResponse(404)
        if self._behavior == "empty":
            return _FakeResponse(200, {"documents": []})
        if self._behavior == "ok":
            return _FakeResponse(200, self._payload or {"documents": []})
        raise RuntimeError(f"unknown behavior: {self._behavior}")


def _patch_client(monkeypatch, behavior: str, payload: dict | None = None):
    def _factory(*args, **kwargs):
        return _FakeAsyncClient(behavior, payload)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


def _set_api_key(monkeypatch):
    monkeypatch.setattr(kakao_maps.settings, "KAKAO_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(kakao_maps.settings, "KAKAO_REST_API_KEY", "test-key", raising=False)


def test_search_keyword_5xx_raises_kakao_api_error(monkeypatch):
    """5xx 응답 → KakaoApiError raise."""
    _set_api_key(monkeypatch)
    _patch_client(monkeypatch, "5xx")
    with pytest.raises(KakaoApiError) as exc_info:
        asyncio.run(search_keyword("강남 한식"))
    assert "5xx" in str(exc_info.value) or "503" in str(exc_info.value)


def test_search_keyword_timeout_raises_kakao_api_error(monkeypatch):
    """타임아웃 → KakaoApiError raise."""
    _set_api_key(monkeypatch)
    _patch_client(monkeypatch, "timeout")
    with pytest.raises(KakaoApiError):
        asyncio.run(search_keyword("강남 한식"))


def test_search_keyword_network_error_raises_kakao_api_error(monkeypatch):
    """네트워크 오류 → KakaoApiError raise."""
    _set_api_key(monkeypatch)
    _patch_client(monkeypatch, "network")
    with pytest.raises(KakaoApiError):
        asyncio.run(search_keyword("강남 한식"))


def test_search_keyword_empty_returns_empty_list(monkeypatch):
    """정상 200 + documents=[] → [] 반환 (장애 아님)."""
    _set_api_key(monkeypatch)
    _patch_client(monkeypatch, "empty")
    result = asyncio.run(search_keyword("강남 한식"))
    assert result == []


def test_search_keyword_404_returns_empty(monkeypatch):
    """4xx (404 등)은 정상 빈 응답으로 처리 → []."""
    _set_api_key(monkeypatch)
    _patch_client(monkeypatch, "404")
    result = asyncio.run(search_keyword("강남 한식"))
    assert result == []


def test_search_address_5xx_raises_kakao_api_error(monkeypatch):
    """search_address도 5xx은 KakaoApiError."""
    _set_api_key(monkeypatch)
    _patch_client(monkeypatch, "5xx")
    with pytest.raises(KakaoApiError):
        asyncio.run(search_address("강남"))


def test_search_address_timeout_raises_kakao_api_error(monkeypatch):
    """search_address timeout → KakaoApiError."""
    _set_api_key(monkeypatch)
    _patch_client(monkeypatch, "timeout")
    with pytest.raises(KakaoApiError):
        asyncio.run(search_address("강남"))


def test_search_address_empty_returns_none(monkeypatch):
    """정상 0건 → None (장애 아님)."""
    _set_api_key(monkeypatch)
    _patch_client(monkeypatch, "empty")
    result = asyncio.run(search_address("강남"))
    assert result is None
