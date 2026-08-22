import {
  ensureIdempotencyKey,
  getHttpErrorCode,
  requestWithPolicy,
  responseToHttpError,
  type HttpErrorBody,
} from "@rotas/http-contract";

const API_BASE = import.meta.env.VITE_ROTAS_API_BASE_URL ?? "";

export interface AuthState {
  accessToken: string;
  tenantId: string;
  driverId: string;
  deviceId: string;
  driverName: string;
  sessionId: string;
}

export function getAuth(): AuthState | null {
  const token = localStorage.getItem("rotas_access_token");
  const tenantId = localStorage.getItem("rotas_tenant_id");
  const driverId = localStorage.getItem("rotas_driver_id");
  const deviceId = localStorage.getItem("rotas_device_id");
  const driverName = localStorage.getItem("rotas_driver_name") ?? "";
  if (!token || !tenantId || !driverId || !deviceId) return null;
  let sessionId = localStorage.getItem("rotas_session_id");
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem("rotas_session_id", sessionId);
  }
  return {
    accessToken: token,
    tenantId,
    driverId,
    deviceId,
    driverName,
    sessionId,
  };
}

function setAuth(auth: AuthState) {
  localStorage.setItem("rotas_access_token", auth.accessToken);
  localStorage.setItem("rotas_tenant_id", auth.tenantId);
  localStorage.setItem("rotas_driver_id", auth.driverId);
  localStorage.setItem("rotas_device_id", auth.deviceId);
  localStorage.setItem("rotas_driver_name", auth.driverName);
  localStorage.setItem("rotas_session_id", auth.sessionId);
}

let _authGeneration = 0;

export function clearAuth() {
  _authGeneration += 1;
  _refreshPromise = null;
  [
    "rotas_access_token",
    "rotas_tenant_id",
    "rotas_driver_id",
    "rotas_device_id",
    "rotas_driver_name",
    "rotas_session_id",
    "rotas_refresh_token", // AUTH-02: clean up on logout/re-pair
  ].forEach((k) => localStorage.removeItem(k));
}

// AUTH-02: In-memory refresh lock — prevents parallel refresh races.
// When multiple API calls fire with an expired token, only the first triggers a network
// refresh. All concurrent callers share the same Promise and reuse the result.
// This is required because token rotation invalidates the refresh_token on first use.
let _refreshPromise: Promise<string | null> | null = null;

export async function refreshDriverAccessToken(): Promise<string | null> {
  if (_refreshPromise) return _refreshPromise;
  const refreshGeneration = _authGeneration;

  const refreshToken = localStorage.getItem("rotas_refresh_token");
  if (!refreshToken) {
    // No refresh token stored — session cannot be refreshed, signal expiry
    window.dispatchEvent(new CustomEvent("session-expired"));
    return null;
  }

  _refreshPromise = requestWithPolicy(
    `${API_BASE}/api/v1/auth/refresh`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    },
    { maxRetries: 0 },
  )
    .then(async (res) => {
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as HttpErrorBody;
        const code = getHttpErrorCode(body);
        // Distinguish access revocation from token expiry (per D-08 / CONTEXT.md)
        if (code === "driver_access_revoked") {
          window.dispatchEvent(new CustomEvent("driver-access-revoked"));
        } else {
          window.dispatchEvent(new CustomEvent("session-expired"));
        }
        localStorage.removeItem("rotas_refresh_token");
        return null;
      }
      const data = (await res.json()) as { access_token: string; refresh_token?: string };
      if (refreshGeneration !== _authGeneration || !getAuth()) {
        return null;
      }
      localStorage.setItem("rotas_access_token", data.access_token);
      if (data.refresh_token) {
        // Rotate: always store the new refresh_token, old one is now invalid
        localStorage.setItem("rotas_refresh_token", data.refresh_token);
      }
      return data.access_token;
    })
    .finally(() => {
      _refreshPromise = null;
    });

  return _refreshPromise;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const auth = getAuth();
  let headers = new Headers(options?.headers);
  if (!headers.has("Content-Type") && options?.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    headers.set("Authorization", `Bearer ${auth.accessToken}`);
    headers.set("X-Tenant-Id", auth.tenantId);
  }
  const method = (options?.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers = ensureIdempotencyKey(headers);
  }

  let res = await requestWithPolicy(`${API_BASE}${path}`, { ...options, headers });

  // AUTH-02: silent refresh on 401 — retry once with a fresh token
  if (res.status === 401) {
    const newToken = await refreshDriverAccessToken();
    if (newToken) {
      const newAuth = getAuth();
      const retryHeaders = new Headers(headers);
      if (newAuth) {
        retryHeaders.set("Authorization", `Bearer ${newToken}`);
        retryHeaders.set("X-Tenant-Id", newAuth.tenantId);
      }
      res = await requestWithPolicy(`${API_BASE}${path}`, {
        ...options,
        headers: retryHeaders,
      });
    }
  }

  if (!res.ok) {
    throw await responseToHttpError(res);
  }
  return res.json() as Promise<T>;
}

export async function pairDevice(pairingCode: string, deviceId: string): Promise<AuthState> {
  const data = await request<{
    access_token: string;
    refresh_token: string; // AUTH-02: backend returns refresh_token on pairing
    driver: { id: string; tenant_id: string; full_name: string };
  }>("/api/v1/driver-auth/pair", {
    method: "POST",
    body: JSON.stringify({ pairing_code: pairingCode, device_id: deviceId, device_name: "ROTAS App" }),
  });
  const auth: AuthState = {
    accessToken: data.access_token,
    tenantId: String(data.driver.tenant_id),
    driverId: String(data.driver.id),
    deviceId,
    driverName: data.driver.full_name,
    sessionId: crypto.randomUUID(),
  };
  setAuth(auth);
  // AUTH-02: store refresh_token for silent token refresh on reconnect
  // Backend returns refresh_token on pairing — previously discarded (bug fix)
  localStorage.setItem("rotas_refresh_token", data.refresh_token);
  return auth;
}

export interface ChecklistTemplate {
  id: string;
  name: string;
  type: string;
  items: Array<{
    id: string;
    label: string;
    type: string;
    is_blocking?: boolean;
    requires_photo?: boolean;
  }>;
}

export interface ActiveTrip {
  id: string;
  origin: string;
  destination: string;
  status: string;
  billing_status: string;
  load_state: string | null;
  vehicle_id: string;
  vehicle_plate?: string | null;
}

export interface BootstrapData {
  profile: {
    tenant_id: string;
    driver_id: string;
    device_id: string | null;
  };
  checklistTemplates: ChecklistTemplate[];
  activeTrip: ActiveTrip | null;
  vehicles: Vehicle[];
}

export async function bootstrap(): Promise<BootstrapData> {
  const auth = getAuth();
  if (!auth) throw new Error("Não autenticado");

  return request<BootstrapData>("/api/v1/driver/bootstrap");
}

export interface Vehicle {
  id: string;
  plate: string;
  brand: string;
  model: string;
  current_km: number;
  status: string;
}

export async function getVehicles(): Promise<Vehicle[]> {
  return request<Vehicle[]>("/api/v1/driver/vehicles?limit=50");
}

export async function createTrip(payload: {
  vehicle_id: string;
  driver_id: string;
  origin: string;
  destination: string;
  cargo_type?: string;
  load_state?: string;
}): Promise<ActiveTrip> {
  return request<ActiveTrip>("/api/v1/driver/trips", { method: "POST", body: JSON.stringify(payload) });
}
