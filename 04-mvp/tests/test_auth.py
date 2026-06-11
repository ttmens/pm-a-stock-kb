"""Test auth middleware."""
import pytest
from api.middleware.auth import auth_middleware, API_TOKEN
from unittest.mock import AsyncMock, MagicMock
from fastapi.responses import JSONResponse


def _make_request(path, headers=None, method="GET"):
    """Create a mock request."""
    request = MagicMock()
    request.url = MagicMock()
    request.url.path = path
    request.method = method
    request.headers = headers or {}
    return request


def test_public_path_no_auth():
    """Public paths don't require auth."""
    request = _make_request("/api/health")
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    # auth_middleware is async, so we need an event loop
    import asyncio
    resp = asyncio.get_event_loop().run_until_complete(auth_middleware(request, call_next))
    call_next.assert_called_once()


def test_missing_auth_header():
    """Missing Authorization header returns 401."""
    request = _make_request("/api/events/600519.SH")
    import asyncio
    resp = asyncio.get_event_loop().run_until_complete(auth_middleware(request, AsyncMock()))
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 401


def test_invalid_token():
    """Invalid token returns 403."""
    request = _make_request("/api/events/600519.SH", headers={"Authorization": "Bearer wrong-token"})
    import asyncio
    resp = asyncio.get_event_loop().run_until_complete(auth_middleware(request, AsyncMock()))
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 403


def test_valid_token():
    """Valid token passes through."""
    request = _make_request("/api/events/600519.SH", headers={"Authorization": "Bearer " + API_TOKEN})
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    import asyncio
    resp = asyncio.get_event_loop().run_until_complete(auth_middleware(request, call_next))
    call_next.assert_called_once()


def test_stock_search_is_public():
    """GET /api/stocks is public for MVP convenience."""
    request = _make_request("/api/stocks", method="GET")
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    import asyncio
    resp = asyncio.get_event_loop().run_until_complete(auth_middleware(request, call_next))
    call_next.assert_called_once()


def test_api_token_default():
    """Default API token is set."""
    assert API_TOKEN == "demo-token-123"
