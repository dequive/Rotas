"use client";

import { bffFetch } from "./bff";
import type {
  TripOrder,
  TripOrderAssignmentResponse,
  TripOrderConfirmPayload,
  TripOrderCreatePayload,
} from "./trip-orders-api";

export function createTripOrder(
  payload: TripOrderCreatePayload,
): Promise<TripOrder> {
  return bffFetch<TripOrder>("/api/v1/trip-orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function confirmTripOrder(
  orderId: string,
  payload: TripOrderConfirmPayload,
): Promise<TripOrder> {
  return bffFetch<TripOrder>(`/api/v1/trip-orders/${orderId}/confirm`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function assignTripOrder(
  orderId: string,
  vehicleId: string,
  driverId: string,
): Promise<TripOrderAssignmentResponse> {
  return bffFetch<TripOrderAssignmentResponse>(
    `/api/v1/trip-orders/${orderId}/assign`,
    {
      method: "POST",
      body: JSON.stringify({ vehicle_id: vehicleId, driver_id: driverId }),
    },
  );
}
