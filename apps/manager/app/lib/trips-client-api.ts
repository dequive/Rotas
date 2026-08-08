"use client";

import { bffFetch } from "./bff";
import type { Trip } from "./trips-api";

export function loadTrips(status?: string): Promise<Trip[]> {
  const query = status ? `?status=${encodeURIComponent(status)}&limit=200` : "?limit=200";
  return bffFetch<Trip[]>(`/api/v1/trips${query}`);
}

export function startTrip(id: string): Promise<Trip> {
  return bffFetch<Trip>(`/api/v1/trips/${id}/start`, { method: "POST" });
}

export function completeTrip(id: string, payload: { km_end: number }): Promise<Trip> {
  return bffFetch<Trip>(`/api/v1/trips/${id}/complete`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function dispatchTrip(id: string): Promise<Trip> {
  return bffFetch<Trip>(`/api/v1/trips/${id}/dispatch`, { method: "POST" });
}

export function closeTrip(
  id: string,
  payload: { pod_received: boolean; pod_waiver: boolean },
): Promise<Trip> {
  return bffFetch<Trip>(`/api/v1/trips/${id}/close`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
