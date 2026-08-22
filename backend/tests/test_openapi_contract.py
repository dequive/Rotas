from scripts.export_openapi import (
    DEFAULT_OUTPUT,
    build_contract,
    serialize_contract,
)


def test_committed_openapi_contract_matches_application() -> None:
    assert DEFAULT_OUTPUT.is_file(), "Generate backend/openapi/rotas-v1.json."
    assert DEFAULT_OUTPUT.read_bytes() == serialize_contract(build_contract())


def test_openapi_contract_exposes_versioned_api() -> None:
    paths = build_contract()["paths"]
    assert len(paths) >= 295
    unversioned_paths = {
        path for path in paths if not path.startswith("/api/v1/")
    }
    assert unversioned_paths == {
        "/health/deep",
        "/version",
    }


def test_f11_workshop_operations_have_explicit_success_schemas() -> None:
    contract = build_contract()
    operations = {
        ("get", "/api/v1/tenants/me"),
        ("patch", "/api/v1/tenants/me"),
        ("get", "/api/v1/vehicles"),
        ("post", "/api/v1/vehicles"),
        ("get", "/api/v1/vehicles/{vehicle_id}"),
        ("patch", "/api/v1/vehicles/{vehicle_id}"),
        ("get", "/api/v1/workshop/work-orders"),
        ("post", "/api/v1/workshop/work-orders"),
        ("get", "/api/v1/workshop/maintenance-requests"),
        ("post", "/api/v1/workshop/maintenance-requests"),
        ("get", "/api/v1/workshop/maintenance-requests/{request_id}"),
        ("post", "/api/v1/workshop/maintenance-requests/{request_id}/notes"),
        ("get", "/api/v1/workshop/maintenance-requests/{request_id}/notes"),
        ("patch", "/api/v1/workshop/maintenance-requests/{request_id}/status"),
    }

    for method, path in operations:
        responses = contract["paths"][path][method]["responses"]
        success = next(
            response
            for status, response in responses.items()
            if str(status).startswith("2")
        )
        schema = success["content"]["application/json"]["schema"]
        assert schema not in ({}, None), f"{method.upper()} {path} has an empty success schema"


def test_f01_authentication_operations_have_explicit_success_schemas() -> None:
    contract = build_contract()
    operations = {
        ("post", "/api/v1/auth/login"),
        ("post", "/api/v1/auth/mfa/verify"),
        ("get", "/api/v1/auth/mfa"),
        ("post", "/api/v1/auth/mfa/setup"),
        ("post", "/api/v1/auth/mfa/confirm"),
        ("delete", "/api/v1/auth/mfa"),
        ("post", "/api/v1/auth/password-reset/request"),
        ("post", "/api/v1/auth/password-reset/complete"),
        ("get", "/api/v1/auth/sessions"),
    }

    for method, path in operations:
        responses = contract["paths"][path][method]["responses"]
        success = next(
            response
            for status, response in responses.items()
            if str(status).startswith("2")
        )
        schema = success["content"]["application/json"]["schema"]
        assert schema not in ({}, None), f"{method.upper()} {path} has an empty success schema"


def test_f02_commercial_trip_order_operations_have_explicit_success_schemas() -> None:
    contract = build_contract()
    operations = {
        ("get", "/api/v1/clients"),
        ("post", "/api/v1/clients"),
        ("get", "/api/v1/clients/{client_id}"),
        ("patch", "/api/v1/clients/{client_id}"),
        ("get", "/api/v1/contracts/"),
        ("post", "/api/v1/contracts/"),
        ("get", "/api/v1/contracts/{contract_id}"),
        ("patch", "/api/v1/contracts/{contract_id}"),
        ("get", "/api/v1/trip-orders"),
        ("post", "/api/v1/trip-orders"),
        ("get", "/api/v1/trip-orders/{order_id}"),
        ("post", "/api/v1/trip-orders/{order_id}/confirm"),
        ("post", "/api/v1/trip-orders/{order_id}/assign"),
        ("post", "/api/v1/trip-orders/{order_id}/cancel"),
    }

    for method, path in operations:
        responses = contract["paths"][path][method]["responses"]
        success = next(
            response
            for status, response in responses.items()
            if str(status).startswith("2")
        )
        schema = success["content"]["application/json"]["schema"]
        assert schema not in ({}, None), f"{method.upper()} {path} has an empty success schema"


def test_f02_trip_lifecycle_operations_have_explicit_success_schemas() -> None:
    contract = build_contract()
    operations = {
        ("get", "/api/v1/trips"),
        ("post", "/api/v1/trips"),
        ("post", "/api/v1/trips/{trip_id}/start"),
        ("post", "/api/v1/trips/{trip_id}/dispatch-clearance/request"),
        ("get", "/api/v1/trips/dispatch-clearances"),
        ("post", "/api/v1/trips/{trip_id}/dispatch-clearance/approve"),
        ("post", "/api/v1/trips/{trip_id}/dispatch"),
        ("post", "/api/v1/trips/{trip_id}/complete"),
        ("post", "/api/v1/trips/{trip_id}/close"),
    }

    for method, path in operations:
        responses = contract["paths"][path][method]["responses"]
        success = next(
            response
            for status, response in responses.items()
            if str(status).startswith("2")
        )
        schema = success["content"]["application/json"]["schema"]
        assert schema not in ({}, None), f"{method.upper()} {path} has an empty success schema"


def test_manager_alert_notification_and_user_operations_have_success_schemas() -> None:
    contract = build_contract()
    operations = {
        ("get", "/api/v1/alerts"),
        ("post", "/api/v1/alerts"),
        ("patch", "/api/v1/alerts/{alert_id}/status"),
        ("post", "/api/v1/notifications/email"),
        ("get", "/api/v1/notifications"),
        ("get", "/api/v1/notifications/{notification_id}"),
        ("get", "/api/v1/users"),
        ("post", "/api/v1/users"),
        ("patch", "/api/v1/users/{user_id}"),
    }

    for method, path in operations:
        responses = contract["paths"][path][method]["responses"]
        success = next(
            response
            for status, response in responses.items()
            if str(status).startswith("2")
        )
        schema = success["content"]["application/json"]["schema"]
        assert schema not in ({}, None), f"{method.upper()} {path} has an empty success schema"


def test_manager_driver_operations_have_explicit_success_schemas() -> None:
    contract = build_contract()
    operations = {
        ("get", "/api/v1/drivers"),
        ("post", "/api/v1/drivers"),
        ("get", "/api/v1/drivers/{driver_id}"),
        ("patch", "/api/v1/drivers/{driver_id}"),
        ("post", "/api/v1/drivers/{driver_id}/pairing-code"),
        ("get", "/api/v1/drivers/{driver_id}/scorecard"),
        ("get", "/api/v1/drivers/{driver_id}/history"),
    }

    for method, path in operations:
        responses = contract["paths"][path][method]["responses"]
        success = next(
            response
            for status, response in responses.items()
            if str(status).startswith("2")
        )
        schema = success["content"]["application/json"]["schema"]
        assert schema not in ({}, None), f"{method.upper()} {path} has an empty success schema"


def test_manager_known_route_operations_have_typed_contracts() -> None:
    contract = build_contract()
    operations = {
        ("get", "/api/v1/known-routes"),
        ("post", "/api/v1/known-routes"),
        ("patch", "/api/v1/known-routes/{route_id}"),
        ("delete", "/api/v1/known-routes/{route_id}"),
    }

    for method, path in operations:
        operation = contract["paths"][path][method]
        success = next(
            response
            for status, response in operation["responses"].items()
            if str(status).startswith("2")
        )
        schema = success["content"]["application/json"]["schema"]
        assert schema not in ({}, None), f"{method.upper()} {path} has an empty success schema"

    for method, path in {
        ("post", "/api/v1/known-routes"),
        ("patch", "/api/v1/known-routes/{route_id}"),
    }:
        schema = contract["paths"][path][method]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        assert "$ref" in schema, f"{method.upper()} {path} accepts an untyped object"


def test_driver_and_sync_operations_have_explicit_public_contracts() -> None:
    contract = build_contract()
    successful_operations = {
        ("get", "/api/v1/driver/bootstrap"),
        ("get", "/api/v1/driver/checklist-templates"),
        ("get", "/api/v1/driver/active-trip"),
        ("get", "/api/v1/driver/trips"),
        ("get", "/api/v1/driver/trips/history"),
        ("post", "/api/v1/sync/batch"),
        ("get", "/api/v1/sync/bootstrap"),
    }
    forbidden_operations = {
        ("get", "/api/v1/driver/vehicles"),
        ("post", "/api/v1/driver/trips"),
    }

    for method, path in successful_operations:
        operation = contract["paths"][path][method]
        success_schemas = [
            response.get("content", {}).get("application/json", {}).get("schema")
            for status, response in operation["responses"].items()
            if str(status).startswith("2")
        ]
        assert success_schemas, f"{method.upper()} {path} has no success response"
        assert all(schema not in ({}, None) for schema in success_schemas), (
            f"{method.upper()} {path} has an empty success schema"
        )

    for method, path in forbidden_operations:
        responses = contract["paths"][path][method]["responses"]
        assert not any(str(status).startswith("2") for status in responses), (
            f"{method.upper()} {path} advertises a success the Driver can never receive"
        )
        forbidden_schema = responses["403"]["content"]["application/json"]["schema"]
        assert forbidden_schema not in ({}, None)

    driver_trip = contract["components"]["schemas"]["DriverTripRead"]
    forbidden_fields = {
        "tenant_id",
        "contract_id",
        "billing_status",
        "billing_document_id",
        "total_fuel_cost",
        "total_expense_cost",
        "total_transport_cost",
        "actual_revenue",
        "actual_margin",
        "costs_reconciled_at",
    }
    assert forbidden_fields.isdisjoint(driver_trip["properties"])
