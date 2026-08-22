from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.accounting.models import Account
from app.modules.accounting.services import _resolve_account_uuid


@pytest.mark.asyncio
async def test_account_number_resolution_awaits_async_database_query(db, tenant_id):
    code = f"62-{uuid4().hex[:8]}"
    account = Account(
        tenant_id=tenant_id,
        code=code,
        name="Serviços externos",
        account_type="Expense",
    )
    db.add(account)
    await db.flush()

    resolved = await _resolve_account_uuid(
        SimpleNamespace(account_number=code),
        tenant_id,
        db,
    )

    assert resolved == account.id
