import { apiFetch } from "./api";
import type { components } from "../generated/rotas-api";

export type TripOrderCreatePayload = components["schemas"]["TripOrderCreate"];
export type TripOrderConfirmPayload = components["schemas"]["TripOrderConfirmRequest"];

export interface TripOrder {
  id: string;
  tenant_id: string;
  contract_id: string | null;
  client_id: string | null;
  customer_reference: string | null;
  origin: string;
  destination: string;
  cargo_type: string | null;
  estimated_weight: number | null;
  status: string; // 'draft', 'confirmed', 'planning', 'assigned', 'execution', 'completed', 'cancelled'
  requested_pickup_date: string;
  created_at: string;
}

export interface TripOrderAssignmentResponse {
  trip_order: TripOrder;
  trip: import("./trips-api").Trip;
}

export async function loadPendingTripOrders(): Promise<TripOrder[]> {
  const statuses = ["draft", "confirmed", "planning"] as const;
  const groups = await Promise.all(
    statuses.map(async (status) => {
      try {
        return await apiFetch<TripOrder[]>(
          `/api/v1/trip-orders?status=${status}&limit=50`,
          { revalidate: 0 },
        );
      } catch {
        return [];
      }
    }),
  );
  return groups.flat();
}

export async function createTripOrder(
  payload: TripOrderCreatePayload,
): Promise<TripOrder> {
  return apiFetch<TripOrder>("/api/v1/trip-orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function confirmTripOrder(
  orderId: string,
  payload: TripOrderConfirmPayload = {},
): Promise<TripOrder> {
  return apiFetch<TripOrder>(`/api/v1/trip-orders/${orderId}/confirm`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function assignTripOrder(orderId: string, vehicleId: string, driverId: string): Promise<TripOrderAssignmentResponse> {
  return apiFetch<TripOrderAssignmentResponse>(`/api/v1/trip-orders/${orderId}/assign`, {
    method: "POST",
    body: JSON.stringify({ vehicle_id: vehicleId, driver_id: driverId }),
  });
}
