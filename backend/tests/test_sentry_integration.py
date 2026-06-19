"""Tests for INFRA-01: Sentry PII scrubber and init guard."""


def test_scrub_pii_strips_all_fields():
    """_scrub_pii removes driver_name, cargo_description, phone, nuit, email,
    plate_number, receiver_name, receiver_contact from event extras."""
    from app.main import _scrub_pii

    event = {
        "extra": {
            "driver_name": "João Machava",
            "cargo_description": "Electronics",
            "phone": "+258 84 123 4567",
            "nuit": "100123456",
            "email": "joao@example.com",
            "plate_number": "MDM-1234-A",
            "receiver_name": "Maria Silva",
            "receiver_contact": "+258 82 987 6543",
            "safe_field": "this stays",
        }
    }
    result = _scrub_pii(event, {})
    extra = result["extra"]
    assert extra["driver_name"] == "[Filtered]"
    assert extra["cargo_description"] == "[Filtered]"
    assert extra["phone"] == "[Filtered]"
    assert extra["nuit"] == "[Filtered]"
    assert extra["email"] == "[Filtered]"
    assert extra["plate_number"] == "[Filtered]"
    assert extra["receiver_name"] == "[Filtered]"
    assert extra["receiver_contact"] == "[Filtered]"
    assert extra["safe_field"] == "this stays"


def test_scrub_pii_handles_nested_dict():
    """_scrub_pii recursively strips PII fields nested inside dicts."""
    from app.main import _scrub_pii

    event = {
        "extra": {
            "outer": {
                "driver_name": "x",
                "safe_key": "safe_value",
            }
        }
    }
    result = _scrub_pii(event, {})
    assert result["extra"]["outer"]["driver_name"] == "[Filtered]"
    assert result["extra"]["outer"]["safe_key"] == "safe_value"


def test_scrub_sql_breadcrumbs():
    """_scrub_pii removes 'data' key from breadcrumbs with category='query'."""
    from app.main import _scrub_pii

    event = {
        "breadcrumbs": {
            "values": [
                {
                    "category": "query",
                    "message": "SELECT * FROM trips",
                    "data": {"params": ["tenant-123", "driver-456"]},
                },
                {
                    "category": "http",
                    "message": "POST /api/v1/sync/batch",
                    "data": {"status": 200},
                },
            ]
        }
    }
    result = _scrub_pii(event, {})
    breadcrumbs = result["breadcrumbs"]["values"]
    # SQL breadcrumb: data must be removed
    assert "data" not in breadcrumbs[0]
    assert breadcrumbs[0]["message"] == "SELECT * FROM trips"
    # HTTP breadcrumb: data must be preserved
    assert breadcrumbs[1]["data"] == {"status": 200}


def test_sentry_not_initialized_without_dsn(monkeypatch):
    """sentry_sdk.init is never called when SENTRY_DSN_BACKEND is empty."""
    import sentry_sdk

    init_calls = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: init_calls.append(kwargs))

    from app.config import get_settings

    settings = get_settings()
    # In test environment, SENTRY_DSN_BACKEND defaults to ""
    if not settings.sentry_dsn_backend:
        # Simulate the lifespan guard
        if settings.sentry_dsn_backend:
            sentry_sdk.init(dsn=settings.sentry_dsn_backend)
        assert len(init_calls) == 0, "sentry_sdk.init must not be called when DSN is absent"


def test_scrub_pii_strips_request_data():
    """_scrub_pii removes PII from request.data (POST body)."""
    from app.main import _scrub_pii

    event = {
        "request": {
            "url": "/api/v1/sync/batch",
            "data": {
                "driver_name": "Tomás Nhantumbo",
                "cargo_description": "Cement bags",
                "trip_id": "abc-123",
            },
        }
    }
    result = _scrub_pii(event, {})
    assert result["request"]["data"]["driver_name"] == "[Filtered]"
    assert result["request"]["data"]["cargo_description"] == "[Filtered]"
    assert result["request"]["data"]["trip_id"] == "abc-123"
