from prometheus_client import generate_latest

from app.database import admin_engine, engine


def _pool_metric_lines() -> list[str]:
    return [
        line
        for line in generate_latest().decode().splitlines()
        if line.startswith("rotas_db_pool_") and not line.startswith("#")
    ]


def test_database_pool_metrics_are_exported_with_bounded_labels():
    lines = _pool_metric_lines()
    payload = "\n".join(lines)

    assert "rotas_db_pool_connections" in payload
    assert "rotas_db_pool_capacity" in payload
    assert "rotas_db_pool_checkouts_total" in payload
    assert "rotas_db_pool_invalidations_total" in payload
    assert 'state="checked_out"' in payload
    assert 'limit="max_connections"' in payload

    for forbidden in ("tenant_id", "user_id", "document_id", "connection_id", "query"):
        assert forbidden not in payload
    assert any(
        f'pool="{pool_name}"' in payload
        for pool_name in ("application", "administrative", "shared")
    )


def test_database_pool_metrics_match_engine_topology():
    payload = "\n".join(_pool_metric_lines())

    if admin_engine is engine:
        assert 'pool="shared"' in payload
        assert 'pool="application"' not in payload
        assert 'pool="administrative"' not in payload
    else:
        assert 'pool="application"' in payload
        assert 'pool="administrative"' in payload
        assert 'pool="shared"' not in payload
