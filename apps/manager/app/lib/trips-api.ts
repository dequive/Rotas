import { apiFetch } from "./api";

export interface Trip {
  id: string;
  vehicle_id: string;
  driver_id: string;
  vehicle_plate: string | null;
  driver_name: string | null;
  origin: string;
  destination: string;
  cargo_type: string | null;
  load_state: string | null;
  status: string;
  billing_status: string;
  actual_departure: string | null;
  actual_arrival: string | null;
  km_start: number | null;
  km_end: number | null;
  created_at: string;
}

export interface CreateTripPayload {
  vehicle_id: string;
  driver_id: string;
  origin: string;
  destination: string;
  cargo_type?: string;
  load_state?: string;
  contract_id?: string;
  planned_departure?: string;
  distance_km?: number;
}

export async function loadTrips(status?: string): Promise<Trip[]> {
  try {
    const qs = status ? `?status=${status}&limit=200` : "?limit=200";
    return await apiFetch<Trip[]>(`/api/v1/trips${qs}`, { revalidate: 10 });
  } catch {
    return [];
  }
}

async function createTrip(payload: CreateTripPayload): Promise<Trip> {
  return apiFetch<Trip>("/api/v1/trips", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function startTrip(id: string): Promise<Trip> {
  return apiFetch<Trip>(`/api/v1/trips/${id}/start`, { method: "POST" });
}

async function completeTrip(id: string, payload: { km_end: number }): Promise<Trip> {
  return apiFetch<Trip>(`/api/v1/trips/${id}/complete`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
