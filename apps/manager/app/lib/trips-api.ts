import { apiFetch } from "./api";
import type { components } from "../generated/rotas-api";

type StartTripPayload = components["schemas"]["StartTripRequest"];
type OperationalCloseTripPayload = components["schemas"]["OperationalCloseTripRequest"];

export interface Trip {
  id: string;
  tenant_id: string;
  trip_order_id: string | null;
  contract_id: string | null;
  vehicle_id: string;
  driver_id: string;
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

export interface TripExecutionEvent {
  id: string;
  tenant_id: string;
  trip_id: string;
  event_type: string;
  event_time: string;
  location?: Record<string, unknown> | null;
  odometer_reading?: number | null;
  fuel_level?: number | null;
  notes?: string | null;
  reported_by?: string | null;
  source: string;
  created_at: string;
}

export interface TripDispatchResponse {
  trip: Trip;
  event: TripExecutionEvent;
}

export async function loadTrips(status?: string): Promise<Trip[]> {
  try {
    const qs = status ? `?status=${status}&limit=200` : "?limit=200";
    return await apiFetch<Trip[]>(`/api/v1/trips${qs}`, { revalidate: 0 });
  } catch {
    return [];
  }
}

export async function createTrip(payload: CreateTripPayload): Promise<Trip> {
  return apiFetch<Trip>("/api/v1/trips", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function startTrip(id: string, payload: StartTripPayload): Promise<Trip> {
  return apiFetch<Trip>(`/api/v1/trips/${id}/start`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function completeTrip(id: string, payload: { km_end: number }): Promise<Trip> {
  return apiFetch<Trip>(`/api/v1/trips/${id}/complete`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function dispatchTrip(id: string): Promise<TripDispatchResponse> {
  return apiFetch<TripDispatchResponse>(`/api/v1/trips/${id}/dispatch`, { method: "POST" });
}

export async function closeTrip(id: string, payload: OperationalCloseTripPayload): Promise<Trip> {
  return apiFetch<Trip>(`/api/v1/trips/${id}/close`, { 
    method: "POST",
    body: JSON.stringify(payload),
  });
}
