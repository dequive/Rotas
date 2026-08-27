import pytest

from app.core.performance_diagnostics import (
    begin_request_timings,
    measure_request_phase,
    observe_request_phase,
    render_server_timing,
    reset_request_timings,
)


def test_request_timings_accumulate_only_allowed_low_cardinality_phases():
    token = begin_request_timings()
    try:
        observe_request_phase("admin_sql", 0.001)
        observe_request_phase("admin_sql", 0.002)
        observe_request_phase("app_sql", 0.004)
        assert render_server_timing() == (
            "admin_sql;dur=3.000, app_sql;dur=4.000"
        )
        with pytest.raises(ValueError):
            observe_request_phase("tenant:personal-id", 1)
    finally:
        reset_request_timings(token)


def test_measurement_is_noop_outside_diagnostic_request():
    with measure_request_phase("auth_identity"):
        pass
    assert render_server_timing() == ""
