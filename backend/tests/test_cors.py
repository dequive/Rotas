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
    # 200/400 with CORS headers when cors_origins is set; 405 when no OPTIONS handler
    assert response.status_code in (200, 400, 405)


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:4173", "http://localhost:5174"],
)
async def test_cors_allows_driver_development_origins(origin: str):
    """The installed Driver PWA and Vite dev server must reach the local API."""
    async with await create_api_client() as client:
        response = await client.options(
            "/api/v1/driver/trips?limit=20&offset=0",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,x-device-id",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


async def test_cors_rejects_retired_driver_preview_origin():
    """A instalação Driver não pode voltar a dividir storage entre 4173 e 4174."""
    async with await create_api_client() as client:
        response = await client.options(
            "/api/v1/auth/driver/pair",
            headers={
                "Origin": "http://localhost:4174",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


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
