import { apiFetch } from "./api";

export interface Driver {
  id: string;
  full_name: string;
  phone: string;
  email: string | null;
  license_number: string;
  license_category: string;
  license_valid_until: string;
  passport_number: string | null;
  passport_valid_until: string | null;
  bi_number: string | null;
  bi_valid_until: string | null;
  employment_type: string;
  status: string;
  score: number;
}

export interface CreateDriverPayload {
  full_name: string;
  phone: string;
  email?: string;
  license_number: string;
  license_category: string;
  license_valid_until: string;
  passport_number?: string;
  passport_valid_until?: string;
  bi_number?: string;
  bi_valid_until?: string;
  employment_type: string;
}

export interface PairingCode {
  pairing_code: string;
  expires_at: string;
}

export async function loadDrivers(): Promise<Driver[]> {
  try {
    return await apiFetch<Driver[]>("/api/v1/drivers?limit=200", { revalidate: 20 });
  } catch {
    return [];
  }
}

async function createDriver(payload: CreateDriverPayload): Promise<Driver> {
  return apiFetch<Driver>("/api/v1/drivers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function updateDriver(id: string, payload: Partial<CreateDriverPayload>): Promise<Driver> {
  return apiFetch<Driver>(`/api/v1/drivers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

async function issuePairingCode(id: string): Promise<PairingCode> {
  return apiFetch<PairingCode>(`/api/v1/drivers/${id}/pairing-code`, { method: "POST" });
}

export interface ScorecardData {
  driver_id: string;
  score: number | null;
  tier: "verde" | "amarelo" | "vermelho" | "insuficiente";
  period_days: number;
  completed_trips: number;
  message?: string;
  metrics: {
    delivery_rate: number;
    sync_score: number;
    distance_score: number;
    stop_score: number;
    total_km: number;
    avg_stop_minutes: number;
  };
}

export async function loadDriverScorecard(
  driverId: string,
  days = 30,
): Promise<ScorecardData | null> {
  try {
    const data = await apiFetch<ScorecardData>(
      `/api/v1/drivers/${driverId}/scorecard?days=${days}`,
    );
    return data;
  } catch {
    return null;
  }
}

export interface DocumentAlert {
  type: string;
  status: string;
  message: string;
}

export interface RecentTrip {
  id: string;
  route_name: string | null;
  status: string;
  date: string;
}

export interface DriverHub360Response {
  driver: Driver;
  recent_trips: RecentTrip[];
  pending_advances_count: number;
  pending_advances_total: number;
  document_alerts: DocumentAlert[];
}

export async function loadDriverHub360(id: string): Promise<DriverHub360Response> {
  return apiFetch<DriverHub360Response>(`/api/v1/drivers/${id}/hub360`, { revalidate: 0 });
}
