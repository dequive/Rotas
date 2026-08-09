import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from core.middleware import RequestIdMiddleware


async def test_request_id_middleware_preserves_original_exception() -> None:
    test_app = FastAPI()
    test_app.add_middleware(RequestIdMiddleware)

    @test_app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("original application failure")

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        with pytest.raises(RuntimeError, match="original application failure"):
            await client.get("/boom")
