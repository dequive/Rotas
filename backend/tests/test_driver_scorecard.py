"""Driver Scorecard — test stubs (D-08 through D-11).

Score formula: 40% delivery proof rate + 25% sync discipline + 20% distance + 15% stop efficiency.
Rolling 30-day window. Score 0-100. Manager only.
"""
import pytest
from app.database import engine, import_all_models

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


@pytest.mark.skip(reason="stub — implement in 04-04-PLAN")
async def test_scorecard_score_range():
    """D-09: get_driver_scorecard() returns a dict with 'score' in 0–100 range
    and 'tier' in ('verde', 'amarelo', 'vermelho', 'insuficiente')."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-04-PLAN")
async def test_scorecard_insufficient_data():
    """D-09/D-10: Driver with fewer than 3 completed trips in rolling 30d returns
    {'score': None, 'tier': 'insuficiente', 'message': 'Mínimo 3 viagens em 30 dias'}."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-04-PLAN")
async def test_scorecard_no_division_by_zero():
    """Pitfall 5: Driver with 0 completed trips returns score=None, not ZeroDivisionError."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-04-PLAN")
async def test_scorecard_api_endpoint_returns_200():
    """D-11: GET /api/v1/drivers/{driver_id}/scorecard returns 200 with scorecard dict
    for manager user. Returns 403 for driver token."""
    pytest.fail("not implemented")
