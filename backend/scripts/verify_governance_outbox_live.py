"""Run one live ROTAS outbox delivery against a configured Governance Engine."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.modules.outbox.models import OutboxEvent
from app.modules.outbox.service import drain_outbox, enqueue
from app.modules.tenants.models import Tenant


async def run(tenant_id: uuid.UUID) -> dict:
    event_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            tenant = Tenant(
                id=tenant_id,
                name="Governance live contract test",
                slug=f"governance-live-{tenant_id.hex[:12]}",
            )
            session.add(tenant)
            await session.flush()

        probe = await enqueue(
            session,
            tenant_id=tenant_id,
            selected_id=event_id,
            event_type="vehicle.breakdown",
            aggregate_type="vehicle",
            aggregate_id=uuid.uuid4(),
            payload={
                "event_type": "vehicle.breakdown",
                "severity": "alta",
                "title": "Live outbox contract verification",
                "description": "Synthetic local production-readiness probe.",
                "occurred_at": datetime.now(UTC),
                "entities": [],
                "idempotency_key": f"rotas:live:{event_id}",
                "payload": {"probe": True},
            },
        )
        # Make this probe deterministic even when the test database contains
        # older pending fixtures: the drainer orders by created_at.
        probe.created_at = datetime(2000, 1, 1, tzinfo=UTC)
        await session.commit()

        counts = await drain_outbox(session, max_rows=1)
        row = await session.scalar(select(OutboxEvent).where(OutboxEvent.id == event_id))
        if row is None:
            raise RuntimeError("Outbox probe row disappeared.")
        await session.refresh(row)
        return {
            "event_id": str(row.id),
            "status": row.status,
            "attempt_count": row.attempt_count,
            "governance_case_id": (
                str(row.governance_case_id) if row.governance_case_id else None
            ),
            "last_error": row.last_error,
            "counts": counts,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=uuid.UUID, required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.tenant_id))
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "sent":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
