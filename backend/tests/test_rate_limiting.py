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


async def test_login_rate_limited_after_10_requests():
    """SEC-03: The 11th login attempt within 1 minute must return HTTP 429."""
    async with await create_api_client() as client:
        for _ in range(10):
            await client.post(
                "/api/v1/auth/login",
                json={"email": "noexist@example.com", "password": "wrong"},
            )
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "noexist@example.com", "password": "wrong"},
        )
    assert response.status_code == 429


async def test_driver_pair_rate_limited_after_10_requests():
    """SEC-03: The 11th /driver-auth/pair attempt within 1 minute must return HTTP 429."""
    async with await create_api_client() as client:
        for _ in range(10):
            await client.post(
                "/api/v1/driver-auth/pair",
                json={"pairing_code": "000000", "device_id": "x", "device_name": "x"},
            )
        response = await client.post(
            "/api/v1/driver-auth/pair",
            json={"pairing_code": "000000", "device_id": "x", "device_name": "x"},
        )
    assert response.status_code == 429
