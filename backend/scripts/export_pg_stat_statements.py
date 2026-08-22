"""Secret-safe pg_stat_statements export for the PR-22 evidence bundle."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

PG_STAT_SQL = """
SELECT
    queryid::bigint AS queryid,
    calls::bigint AS calls,
    round(total_exec_time::numeric, 3)::float8 AS total_exec_time_ms,
    round(mean_exec_time::numeric, 3)::float8 AS mean_exec_time_ms,
    rows::bigint AS rows,
    shared_blks_hit::bigint AS shared_blks_hit,
    shared_blks_read::bigint AS shared_blks_read,
    temp_blks_written::bigint AS temp_blks_written
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY total_exec_time DESC
LIMIT %s
"""
PG_STAT_FIELDS = (
    "queryid",
    "calls",
    "total_exec_time_ms",
    "mean_exec_time_ms",
    "rows",
    "shared_blks_hit",
    "shared_blks_read",
    "temp_blks_written",
)


class PgStatExportError(ValueError):
    pass


def build_report(rows: list[dict[str, Any]], *, limit: int) -> dict[str, Any]:
    if limit < 1 or limit > 1000:
        raise PgStatExportError("limit must be between 1 and 1000.")
    entries = [{field: row[field] for field in PG_STAT_FIELDS} for row in rows]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "extension": "pg_stat_statements",
        "query_text_included": False,
        "limit": limit,
        "entries": entries,
    }


def export_pg_stat_statements(database_url: str, *, limit: int) -> dict[str, Any]:
    if not database_url:
        raise PgStatExportError("ROTAS_PERF_ADMIN_DATABASE_URL is required.")
    dsn = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_extension "
                "WHERE extname = 'pg_stat_statements') AS enabled"
            )
            extension = cursor.fetchone()
            if not extension or extension["enabled"] is not True:
                raise PgStatExportError("pg_stat_statements extension is not enabled.")
            cursor.execute(PG_STAT_SQL, (limit,))
            rows = list(cursor.fetchall())
    if not rows:
        raise PgStatExportError("pg_stat_statements returned no rows for the database.")
    return build_report(rows, limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    try:
        report = export_pg_stat_statements(
            os.environ.get("ROTAS_PERF_ADMIN_DATABASE_URL", ""),
            limit=args.limit,
        )
    except (KeyError, psycopg.Error, PgStatExportError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "entries": len(report["entries"]),
                "query_text_included": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
