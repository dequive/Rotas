import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  cookies: new Map<string, string>(),
  requestHeaders: new Map<string, string>(),
  secretFiles: new Map<string, string>(),
}));

vi.mock("node:fs", () => {
  const readFileSync = (path: string) => {
    const value = state.secretFiles.get(path);
    if (value === undefined) throw new Error("missing secret");
    return value;
  };
  return { default: { readFileSync }, readFileSync };
});

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) => {
      const value = state.cookies.get(name);
      return value ? { value } : undefined;
    },
  })),
  headers: vi.fn(async () => ({
    get: (name: string) =>
      state.requestHeaders.get(name) ??
      state.requestHeaders.get(name.toLowerCase()) ??
      null,
  })),
}));

import { GET, POST } from "../api/governance/cases/route";
import { GET as getCaseTypes } from "../api/governance/case-types/route";
import {
  GET as getTransitions,
  POST as transitionCase,
} from "../api/governance/cases/[id]/transitions/route";

const TENANT_ID = "11111111-1111-4111-8111-111111111111";
const CASE_ID = "22222222-2222-4222-8222-222222222222";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Governance BFF boundary", () => {
  beforeEach(() => {
    state.cookies.clear();
    state.cookies.set("rotas_access_token", "rotas-access-token");
    state.cookies.set("rotas_tenant_id", TENANT_ID);
    state.cookies.set("rotas_user_id", "user-1");
    state.cookies.set("rotas_role", "admin");
    state.requestHeaders.clear();
    state.secretFiles.clear();
    process.env.GOVERNANCE_API_URL = "http://localhost:8001";
    process.env.GOVERNANCE_API_KEYS_BY_TENANT = JSON.stringify({
      [TENANT_ID]: "governance-secret",
    });
    delete process.env.GOVERNANCE_API_KEY;
    delete process.env.GOVERNANCE_TENANT_ID;
    delete process.env.GOVERNANCE_API_KEY_FILE;
    vi.restoreAllMocks();
  });

  afterEach(() => {
    delete process.env.GOVERNANCE_API_URL;
    delete process.env.GOVERNANCE_API_KEYS_BY_TENANT;
    delete process.env.GOVERNANCE_API_KEY;
    delete process.env.GOVERNANCE_TENANT_ID;
    delete process.env.GOVERNANCE_API_KEY_FILE;
  });

  it("fails closed before contacting either upstream when the ROTAS session is absent", async () => {
    state.cookies.clear();
    const upstream = vi.spyOn(globalThis, "fetch");

    const response = await GET(
      new NextRequest("http://manager.local/api/governance/cases"),
    );

    expect(response.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("verifies the ROTAS token tenant before using the tenant-scoped Governance key", async () => {
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ id: TENANT_ID }))
      .mockResolvedValueOnce(
        jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
      );

    const response = await GET(
      new NextRequest("http://manager.local/api/governance/cases?limit=50"),
    );

    expect(response.status).toBe(200);
    expect(upstream).toHaveBeenCalledTimes(2);
    expect(String(upstream.mock.calls[0]?.[0])).toContain("/api/v1/tenants/me");
    expect(String(upstream.mock.calls[1]?.[0])).toBe(
      "http://localhost:8001/api/v1/cases/?limit=50",
    );
    const governanceHeaders = new Headers(
      (upstream.mock.calls[1]?.[1] as RequestInit).headers,
    );
    expect(governanceHeaders.get("X-API-Key")).toBe("governance-secret");
    expect(governanceHeaders.get("Authorization")).toBeNull();
    expect(governanceHeaders.get("X-Tenant-Id")).toBeNull();
  });

  it("rejects a tenant-cookie mismatch and never contacts Governance", async () => {
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse({ id: "33333333-3333-4333-8333-333333333333" }),
      );

    const response = await GET(
      new NextRequest("http://manager.local/api/governance/cases"),
    );
    const body = (await response.json()) as { error: { code: string } };

    expect(response.status).toBe(403);
    expect(body.error.code).toBe("tenant_session_mismatch");
    expect(upstream).toHaveBeenCalledOnce();
  });

  it("loads a single-tenant key from a server-only secret file", async () => {
    delete process.env.GOVERNANCE_API_KEYS_BY_TENANT;
    process.env.GOVERNANCE_TENANT_ID = TENANT_ID;
    process.env.GOVERNANCE_API_KEY_FILE = "/run/secrets/governance_api_key";
    state.secretFiles.set("/run/secrets/governance_api_key", "file-secret\n");
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ id: TENANT_ID }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }));

    const response = await GET(
      new NextRequest("http://manager.local/api/governance/cases"),
    );

    expect(response.status).toBe(200);
    const headers = new Headers((upstream.mock.calls[1]?.[1] as RequestInit).headers);
    expect(headers.get("X-API-Key")).toBe("file-secret");
  });

  it("requires idempotency and sends the canonical case creation contract", async () => {
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ id: TENANT_ID }))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            id: CASE_ID,
            reference: "CASE-2026-0001",
            case_type_code: "internal.request",
            status: "open",
            payload: { title: "Pedido TI", description: "Sem rede" },
          },
          201,
        ),
      );
    const request = new NextRequest(
      "http://manager.local/api/governance/cases",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": "create-case-1",
        },
        body: JSON.stringify({
          case_type_code: "internal.request",
          payload: { title: "Pedido TI", description: "Sem rede" },
        }),
      },
    );

    const response = await POST(request);

    expect(response.status).toBe(201);
    const init = upstream.mock.calls[1]?.[1] as RequestInit;
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe(
      "create-case-1",
    );
    expect(JSON.parse(String(init.body))).toEqual({
      case_type_code: "internal.request",
      occurrence_ids: [],
      payload: { title: "Pedido TI", description: "Sem rede" },
    });
  });

  it("uses the canonical plural transition endpoint and contract", async () => {
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ id: TENANT_ID }))
      .mockResolvedValueOnce(jsonResponse({ to_status: "resolved" }, 201));
    const request = new NextRequest(
      `http://manager.local/api/governance/cases/${CASE_ID}/transitions`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": "transition-1",
        },
        body: JSON.stringify({
          to_status: "resolved",
          reason: "Concluído",
          payload: { resolution_note: "Concluído" },
        }),
      },
    );

    const response = await transitionCase(request, {
      params: Promise.resolve({ id: CASE_ID }),
    });

    expect(response.status).toBe(201);
    expect(String(upstream.mock.calls[1]?.[0])).toBe(
      `http://localhost:8001/api/v1/cases/${CASE_ID}/transitions`,
    );
  });

  it("reads the audited transition history from the canonical endpoint", async () => {
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ id: TENANT_ID }))
      .mockResolvedValueOnce(jsonResponse([]));

    const response = await getTransitions(
      new NextRequest(
        `http://manager.local/api/governance/cases/${CASE_ID}/transitions`,
      ),
      { params: Promise.resolve({ id: CASE_ID }) },
    );

    expect(response.status).toBe(200);
    expect(String(upstream.mock.calls[1]?.[0])).toBe(
      `http://localhost:8001/api/v1/cases/${CASE_ID}/transitions`,
    );
  });

  it("exposes the tenant-scoped case types needed by the creation form", async () => {
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ id: TENANT_ID }))
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: CASE_ID,
            code: "rotas.incident",
            name: "Incidente Operacional",
            initial_status: "open",
            sla_hours: 48,
          },
        ]),
      );

    const response = await getCaseTypes();

    expect(response.status).toBe(200);
    expect(String(upstream.mock.calls[1]?.[0])).toBe(
      "http://localhost:8001/api/v1/cases/types/",
    );
  });

  it("normalizes a malformed Governance response instead of trusting it", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ id: TENANT_ID }))
      .mockResolvedValueOnce(
        new Response("not-json", {
          status: 200,
          headers: { "Content-Type": "text/plain" },
        }),
      );

    const response = await GET(
      new NextRequest("http://manager.local/api/governance/cases"),
    );
    const body = (await response.json()) as { error: { code: string } };

    expect(response.status).toBe(502);
    expect(body.error.code).toBe("invalid_upstream_response");
  });
});
