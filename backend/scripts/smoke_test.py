#!/usr/bin/env python3
"""
Post-deploy smoke test for ROTAS.

Verifies that the API surface is live and the critical flows respond correctly
after a production or staging deploy.

Usage:
    python scripts/smoke_test.py https://your-api.railway.app

Exit code 0 = all checks passed.
Exit code 1 = one or more checks failed.

Environment variables (optional):
    SMOKE_EMAIL     — manager user e-mail for login check (default: admin@rotas.local)
    SMOKE_PASSWORD  — manager user password (default: changeme)
"""

import asyncio
import os
import sys
from typing import Any

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx")
    sys.exit(1)


TIMEOUT = httpx.Timeout(10.0, connect=5.0)
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"
CHECK = f"{GREEN}✓{RESET}"
CROSS = f"{RED}✗{RESET}"
WARN = f"{YELLOW}!{RESET}"


def ok(label: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"  {CHECK} {label}{suffix}")


def fail(label: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"  {CROSS} {label}{suffix}")


def warn(label: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"  {WARN} {label}{suffix}")


async def run(base_url: str) -> int:
    failures = 0
    email = os.getenv("SMOKE_EMAIL", "admin@rotas.local")
    password = os.getenv("SMOKE_PASSWORD", "changeme")

    async with httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT) as client:
        # ── S1: /health ────────────────────────────────────────────────────
        print("\nS1: Health (lightweight)")
        try:
            r = await client.get("/health")
            if r.status_code == 200 and r.json().get("status") == "ok":
                ok("/health", "200 ok")
            else:
                fail("/health", f"status={r.status_code} body={r.text[:100]}")
                failures += 1
        except Exception as e:
            fail("/health", str(e))
            failures += 1

        # ── S2: /health/deep ───────────────────────────────────────────────
        print("\nS2: Health (deep — DB, Redis, ARQ)")
        try:
            r = await client.get("/health/deep")
            body = r.json()
            if r.status_code == 200 and body.get("status") == "ok":
                for svc, status in body.get("checks", {}).items():
                    if "ok" in str(status):
                        ok(svc, status)
                    elif "not_configured" in str(status):
                        warn(svc, status)
                    else:
                        fail(svc, status)
                        failures += 1
            else:
                fail("/health/deep", f"status={r.status_code}")
                for svc, status in body.get("checks", {}).items():
                    if "ok" not in str(status):
                        fail(f"  {svc}", str(status))
                failures += 1
        except Exception as e:
            fail("/health/deep", str(e))
            failures += 1

        # ── S3: /version ───────────────────────────────────────────────────
        print("\nS3: Version")
        try:
            r = await client.get("/version")
            if r.status_code == 200:
                v: dict[str, Any] = r.json()
                ok("/version", f"version={v.get('version')} env={v.get('environment')}")
            else:
                fail("/version", f"status={r.status_code}")
                failures += 1
        except Exception as e:
            fail("/version", str(e))
            failures += 1

        # ── S4: Dashboard login ─────────────────────────────────────────────
        print(f"\nS4: Dashboard login ({email})")
        access_token: str | None = None
        tenant_id: str | None = None
        try:
            r = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            if r.status_code == 200:
                data = r.json()
                access_token = data.get("access_token")
                tenant_id = data.get("tenant_id") or (data.get("user", {}) or {}).get("tenant_id")
                if access_token:
                    ok("login", f"token issued tenant={tenant_id}")
                else:
                    fail("login", "200 but no access_token in response")
                    failures += 1
            elif r.status_code == 401:
                warn("login", f"401 — credentials not seeded? body={r.text[:80]}")
            else:
                fail("login", f"status={r.status_code} body={r.text[:100]}")
                failures += 1
        except Exception as e:
            fail("login", str(e))
            failures += 1

        # ── S5: List vehicles (authenticated) ──────────────────────────────
        print("\nS5: Vehicles list (authenticated)")
        if access_token and tenant_id:
            try:
                r = await client.get(
                    "/api/v1/vehicles?limit=1",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-Tenant-Id": str(tenant_id),
                    },
                )
                if r.status_code == 200:
                    count = len(r.json()) if isinstance(r.json(), list) else "?"
                    ok("GET /vehicles", f"returned {count} item(s)")
                else:
                    fail("GET /vehicles", f"status={r.status_code} body={r.text[:100]}")
                    failures += 1
            except Exception as e:
                fail("GET /vehicles", str(e))
                failures += 1
        else:
            warn("GET /vehicles", "skipped — no auth token")

        # ── S6: Driver pairing code ─────────────────────────────────────────
        print("\nS6: Driver pairing (generate code)")
        if access_token and tenant_id:
            try:
                r = await client.post(
                    "/api/v1/driver-auth/pairing-code",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-Tenant-Id": str(tenant_id),
                    },
                    json={},
                )
                if r.status_code in (200, 201, 404, 422):
                    if r.status_code == 200:
                        code = r.json().get("pairing_code", "?")
                        ok("pairing-code", f"code={code[:4]}***")
                    elif r.status_code == 404:
                        warn("pairing-code", "404 — no driver seeded, expected")
                    else:
                        warn("pairing-code", f"status={r.status_code} body={r.text[:80]}")
                else:
                    fail("pairing-code", f"status={r.status_code} body={r.text[:100]}")
                    failures += 1
            except Exception as e:
                fail("pairing-code", str(e))
                failures += 1
        else:
            warn("pairing-code", "skipped — no auth token")

        # ── S7: Sync batch (unauthenticated → 401) ─────────────────────────
        print("\nS7: Sync batch auth guard")
        try:
            r = await client.post(
                "/api/v1/sync/batch",
                json={"device_id": "smoke-test", "operations": []},
            )
            if r.status_code == 401:
                ok("sync/batch no-auth", "correctly 401 with no token")
            else:
                fail("sync/batch no-auth", f"expected 401, got {r.status_code}")
                failures += 1
        except Exception as e:
            fail("sync/batch no-auth", str(e))
            failures += 1

        # ── S8: Billing documents (manager scope guard) ─────────────────────
        print("\nS8: Billing access guard (unauthenticated → 401)")
        try:
            r = await client.get("/api/v1/billing/documents")
            if r.status_code == 401:
                ok("billing no-auth", "correctly 401 with no token")
            else:
                fail("billing no-auth", f"expected 401, got {r.status_code}")
                failures += 1
        except Exception as e:
            fail("billing no-auth", str(e))
            failures += 1

    # ── Summary ────────────────────────────────────────────────────────────────
    print()
    if failures == 0:
        print(f"{GREEN}All smoke checks passed.{RESET}\n")
    else:
        print(f"{RED}{failures} smoke check(s) FAILED.{RESET}\n")
    return failures


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python smoke_test.py <base-url>")
        print("  e.g. python smoke_test.py https://rotas-api.railway.app")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    print(f"Smoke-testing: {base_url}")

    failures = asyncio.run(run(base_url))
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
