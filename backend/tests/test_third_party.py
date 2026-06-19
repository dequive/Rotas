"""Tests for the third_party module — TP-10: document expiry alert ARQ task."""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


async def test_doc_expiry_alerts():
    """TP-10: Document expiring in 15 days generates 1 alert with correct fields.

    Mocks the DB session and create_alert — no live DB or Redis required.
    """
    doc_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    expiry = date.today() + timedelta(days=15)

    # Mock OperationalDocument ORM row
    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.tenant_id = tenant_id
    mock_doc.subject_type = "driver"
    mock_doc.subject_id = subject_id
    mock_doc.document_type = "license"
    mock_doc.expiry_date = expiry

    captured_alerts: list = []

    async def mock_create_alert(db, tenant_id_arg, payload):
        captured_alerts.append((tenant_id_arg, payload))

    # Build a minimal ARQ ctx with a mock db_factory
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_doc]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)
    ctx = {"db_factory": mock_factory}

    with patch("app.modules.alerts.service.create_alert", side_effect=mock_create_alert):
        from app.worker import task_check_document_expiry

        result = await task_check_document_expiry(ctx)

    assert "1" in result, f"Expected 1 alert in result message, got: {result!r}"
    assert len(captured_alerts) == 1, f"Expected 1 captured alert, got {len(captured_alerts)}"

    _tid, alert = captured_alerts[0]
    assert alert.entity_type == "driver"
    assert alert.entity_id == subject_id
    assert alert.priority == "high", f"15-day expiry should be 'high', got {alert.priority!r}"
    assert f"doc_expiry:{doc_id}" in alert.request_reference
    assert expiry.isoformat() in alert.request_reference
    assert alert.channel == "dashboard"
    assert alert.alert_type == "document_expiring_soon"


async def test_doc_expiry_critical_priority():
    """TP-10: Document expiring in 5 days gets priority='critical'."""
    doc_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    expiry = date.today() + timedelta(days=5)

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.tenant_id = tenant_id
    mock_doc.subject_type = "vehicle"
    mock_doc.subject_id = subject_id
    mock_doc.document_type = "insurance"
    mock_doc.expiry_date = expiry

    captured_alerts: list = []

    async def mock_create_alert(db, tenant_id_arg, payload):
        captured_alerts.append(payload)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_doc]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": MagicMock(return_value=mock_session)}

    with patch("app.modules.alerts.service.create_alert", side_effect=mock_create_alert):
        from app.worker import task_check_document_expiry

        await task_check_document_expiry(ctx)

    assert len(captured_alerts) == 1
    assert captured_alerts[0].priority == "critical", (
        f"5-day expiry should be 'critical', got {captured_alerts[0].priority!r}"
    )


async def test_doc_expiry_alert_error_continues():
    """TP-10: If create_alert raises for one doc, the task continues without aborting."""
    doc_id_1, doc_id_2 = uuid.uuid4(), uuid.uuid4()
    tenant_id = uuid.uuid4()
    expiry_1 = date.today() + timedelta(days=3)
    expiry_2 = date.today() + timedelta(days=20)

    def make_doc(doc_id, expiry, doc_type):
        m = MagicMock()
        m.id = doc_id
        m.tenant_id = tenant_id
        m.subject_type = "driver"
        m.subject_id = uuid.uuid4()
        m.document_type = doc_type
        m.expiry_date = expiry
        return m

    docs = [make_doc(doc_id_1, expiry_1, "passport"), make_doc(doc_id_2, expiry_2, "license")]

    call_count = 0

    async def mock_create_alert_raises_first(db, tenant_id_arg, payload):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("simulated alert failure")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = docs
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": MagicMock(return_value=mock_session)}

    with patch(
        "app.modules.alerts.service.create_alert",
        side_effect=mock_create_alert_raises_first,
    ):
        from app.worker import task_check_document_expiry

        result = await task_check_document_expiry(ctx)

    # First doc raised, second succeeded → 1 alert counted
    assert "1" in result
    assert call_count == 2, "create_alert should have been called for both docs"


async def test_doc_expiry_no_docs():
    """TP-10: No expiring documents → task returns 0 alerts, no errors."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": MagicMock(return_value=mock_session)}

    from app.worker import task_check_document_expiry

    result = await task_check_document_expiry(ctx)
    assert "0" in result


async def test_worker_settings_registration():
    """TP-10: task_check_document_expiry is in WorkerSettings.functions and cron_jobs."""
    from app.worker import WorkerSettings, task_check_document_expiry

    assert task_check_document_expiry in WorkerSettings.functions, (
        "task_check_document_expiry must be in WorkerSettings.functions"
    )
    cron_funcs = [c.coroutine for c in WorkerSettings.cron_jobs]
    assert task_check_document_expiry in cron_funcs, (
        "task_check_document_expiry must be registered in WorkerSettings.cron_jobs"
    )
