"""Stabilization/P0-F4: transaction boundary policy.

Goal: only routers (or top-level use cases) commit. Services `flush()` —
they never own the transaction. This file documents the policy and provides
a helper to wrap multiple service calls in one atomic block.

Migration plan:
  1. Refactor `hr.service.generate_payroll` to remove its inner
     `await db.commit()` and accept rollback on exception (already does via
     SQLAlchemy's session teardown).
  2. Refactor `accounting.services.create_journal_entry` likewise. The
     router already commits, so removing the inner commit_noop is safe.
  3. Adopt the `transactional()` context manager in routers that chain
     multiple service calls (billable-trip creation + journal entry, etc.).

The default in-tree transactions are single-statement atomic enough; this
policy is the seed for P1 hardening.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def transactional(session) -> AsyncIterator[None]:
    """Wrap multiple service calls in a single transaction.

    Usage:
        async with transactional(db):
            payroll = await hr.generate_payroll(...)
            await accounting.create_journal_entry(...)

    If any call raises, the surrounding block is rolled back. Otherwise
    exactly one commit is issued at the end.
    """
    try:
        yield
    except Exception:
        await session.rollback()
        raise
    else:
        await session.commit()