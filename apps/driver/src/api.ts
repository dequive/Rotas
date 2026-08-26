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

async function authorizedRequest(path: string, options?: RequestInit): Promise<Response> {
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
  return res;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await authorizedRequest(path, options);
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
  /** Transitional backend field. Driver clients never receive a fleet selector. */
  vehicles: [];
}

export async function bootstrap(): Promise<BootstrapData> {
  const auth = getAuth();
  if (!auth) throw new Error("Não autenticado");

  return request<BootstrapData>("/api/v1/driver/bootstrap");
}

export interface DriverTrip extends ActiveTrip {
  driver_id: string;
  cargo_type: string | null;
  cargo_class: string | null;
  cargo_weight: number | null;
  requires_load_permit: boolean;
  requires_cargo_manifest: boolean;
  waybill_number: string | null;
  km_start: number | null;
  km_end: number | null;
  planned_departure: string | null;
  actual_departure: string | null;
  planned_arrival: string | null;
  actual_arrival: string | null;
  recipient_name: string | null;
  cargo_status: string | null;
  created_at: string;
  updated_at: string;
}

export interface DriverTripPage {
  items: DriverTrip[];
  total: number;
  limit: number;
  offset: number;
}

export interface DriverTripDocuments {
  trip_id: string;
  complete: boolean;
  can_request: boolean;
  missing_required: string[];
  requirements: Array<{ document_type: string; present: boolean }>;
  documents: Array<{
    id: string;
    document_type: string;
    document_number: string | null;
    status: string;
    file_id: string | null;
    issued_at: string;
  }>;
  requests: DriverDocumentRequest[];
}

export interface DriverDocumentRequest {
  id: string;
  trip_id: string;
  document_type: string;
  status: string;
  note: string | null;
  created_at: string;
}

export interface DriverRecordPage<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface DriverChecklistRecord {
  id: string;
  trip_id: string | null;
  vehicle_id: string;
  checklist_type: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  created_at: string;
}

export interface DriverFuelRecord {
  id: string;
  trip_id: string | null;
  vehicle_id: string;
  fuel_date: string;
  station_name: string | null;
  fuel_type: string;
  liters: string;
  total_cost: string;
  km_at_refuel: number;
  has_receipt: boolean;
  is_verified: boolean;
  is_flagged: boolean;
  created_at: string;
}

export interface DriverExpenseRecord {
  id: string;
  trip_id: string;
  expense_type: string;
  description: string | null;
  amount: string;
  currency: string;
  payment_method: string | null;
  has_receipt: boolean;
  entry_type: "original" | "adjustment" | "reversal";
  corrects_id: string | null;
  correction_reason: string | null;
  recorded_by_type: "driver" | "manager" | "system";
  incurred_at: string;
  created_at: string;
}

export interface DriverAdvanceRecord {
  id: string;
  trip_id: string;
  total_amount: string;
  allowance_amount: string;
  expense_amount: string;
  currency: string;
  status: string;
  issued_at: string;
}

function driverRecordQuery(limit: number, offset: number, tripId?: string): string {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (tripId) params.set("trip_id", tripId);
  return params.toString();
}

export function listDriverChecklistRecords(
  limit = 20,
  offset = 0,
  tripId?: string,
): Promise<DriverRecordPage<DriverChecklistRecord>> {
  return request(`/api/v1/driver/records/checklists?${driverRecordQuery(limit, offset, tripId)}`);
}

export function listDriverFuelRecords(
  limit = 20,
  offset = 0,
  tripId?: string,
): Promise<DriverRecordPage<DriverFuelRecord>> {
  return request(`/api/v1/driver/records/fuel?${driverRecordQuery(limit, offset, tripId)}`);
}

export function listDriverExpenseRecords(
  limit = 20,
  offset = 0,
  tripId?: string,
): Promise<DriverRecordPage<DriverExpenseRecord>> {
  return request(`/api/v1/driver/records/expenses?${driverRecordQuery(limit, offset, tripId)}`);
}

export function listDriverAdvanceRecords(
  limit = 20,
  offset = 0,
  tripId?: string,
): Promise<DriverRecordPage<DriverAdvanceRecord>> {
  return request(`/api/v1/driver/records/advances?${driverRecordQuery(limit, offset, tripId)}`);
}

export function listDriverTrips(limit = 20, offset = 0): Promise<DriverTripPage> {
  return request<DriverTripPage>(`/api/v1/driver/trips?limit=${limit}&offset=${offset}`);
}

export function listDriverTripHistory(limit = 20, offset = 0): Promise<DriverTripPage> {
  return request<DriverTripPage>(
    `/api/v1/driver/trips/history?limit=${limit}&offset=${offset}`,
  );
}

export function getDriverTripDocuments(tripId: string): Promise<DriverTripDocuments> {
  return request<DriverTripDocuments>(`/api/v1/driver/trips/${tripId}/documents`);
}

export function requestDriverTripDocument(
  tripId: string,
  documentType: string,
): Promise<DriverDocumentRequest> {
  return request<DriverDocumentRequest>(
    `/api/v1/driver/trips/${tripId}/document-requests`,
    { method: "POST", body: JSON.stringify({ document_type: documentType }) },
  );
}

export async function downloadDriverTripDocument(
  tripId: string,
  fileId: string,
): Promise<Blob> {
  const response = await authorizedRequest(
    `/api/v1/driver/trips/${tripId}/documents/${fileId}/download`,
  );
  return response.blob();
}
