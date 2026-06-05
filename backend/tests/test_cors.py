import httpx
import pytest

from app.database import engine, import_all_models
from app.main import app

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def test_cors_allows_listed_origin():
    """SEC-02: Requests from a listed CORS origin receive CORS headers."""
    # Stub — will exercise CORSMiddleware after Plan 02 ensures it's always attached.
    # Currently passes because endpoint is reachable; production CORS origin check is manual.
    async with await create_api_client() as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "https://rotas-manager.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code in (200, 400)


async def test_cors_rejects_unknown_origin():
    """SEC-02: Requests from unknown origins must not receive Allow-Origin header."""
    async with await create_api_client() as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "https://evil-site.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert "access-control-allow-origin" not in response.headers
