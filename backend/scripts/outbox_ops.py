"""Tenant-scoped operational CLI for the ROTAS transactional outbox."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from uuid import UUID

import httpx


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate the ROTAS transactional outbox.")
    parser.add_argument(
        "--api-url",
        default=os.getenv("ROTAS_API_URL", "http://localhost:8000"),
        help="ROTAS API base URL (default: ROTAS_API_URL or http://localhost:8000).",
    )
    parser.add_argument("--tenant-id", default=os.getenv("ROTAS_TENANT_ID"))
    parser.set_defaults(token=os.getenv("ROTAS_ACCESS_TOKEN"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("list", help="List outbox events.")
    listing.add_argument(
        "--status",
        choices=("pending", "sent", "dead_letter"),
        dest="status_filter",
    )
    listing.add_argument("--event-type")
    listing.add_argument("--limit", type=int, default=50, choices=range(1, 201))

    show = subparsers.add_parser("show", help="Show an event including its payload.")
    show.add_argument("event_id", type=UUID)

    subparsers.add_parser("reconciliation", help="Show the tenant reconciliation summary.")

    replay = subparsers.add_parser("replay", help="Replay a dead-letter event.")
    replay.add_argument("event_id", type=UUID)
    replay.add_argument("--reason", required=True)
    return parser


def _request_spec(args: argparse.Namespace) -> tuple[str, str, dict[str, Any] | None]:
    if args.command == "list":
        params: dict[str, Any] = {"limit": args.limit}
        if args.status_filter:
            params["status"] = args.status_filter
        if args.event_type:
            params["event_type"] = args.event_type
        return "GET", "/api/v1/outbox-events", {"params": params}
    if args.command == "show":
        return "GET", f"/api/v1/outbox-events/{args.event_id}", None
    if args.command == "reconciliation":
        return "GET", "/api/v1/outbox-events/reconciliation", None
    if args.command == "replay":
        if len(args.reason.strip()) < 10:
            raise ValueError("Replay reason must contain at least 10 characters.")
        return (
            "POST",
            f"/api/v1/outbox-events/{args.event_id}/replay",
            {"json": {"reason": args.reason.strip()}},
        )
    raise ValueError(f"Unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.token:
        parser.error("ROTAS_ACCESS_TOKEN is required")
    if not args.tenant_id:
        parser.error("--tenant-id or ROTAS_TENANT_ID is required")
    try:
        tenant_id = UUID(str(args.tenant_id))
        method, path, options = _request_spec(args)
    except ValueError as exc:
        parser.error(str(exc))

    headers = {
        "Authorization": f"Bearer {args.token}",
        "X-Tenant-Id": str(tenant_id),
    }
    url = f"{args.api_url.rstrip('/')}{path}"
    try:
        response = httpx.request(
            method,
            url,
            headers=headers,
            timeout=15.0,
            **(options or {}),
        )
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc.__class__.__name__}", file=sys.stderr)
        return 2

    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}
    print(json.dumps(body, indent=2, ensure_ascii=False, default=str))
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
