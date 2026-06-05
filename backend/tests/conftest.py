import pytest


@pytest.fixture(autouse=True)
async def reset_rate_limiter_storage():
    """Clear slowapi in-memory counters between tests.

    Without this, rate-limit stub tests (which fire 10+ requests) bleed into
    subsequent tests and cause legitimate requests to get 429.
    """
    from app.core.limiter import limiter

    yield

    if hasattr(limiter, "_storage") and hasattr(limiter._storage, "reset"):
        limiter._storage.reset()
