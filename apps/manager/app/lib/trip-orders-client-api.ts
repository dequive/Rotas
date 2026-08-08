"use client";

import { bffFetch } from "./bff";
import type { TripOrder } from "./trip-orders-api";

export function assignTripOrder(
  orderId: string,
  vehicleId: string,
  driverId: string,
): Promise<TripOrder> {
  return bffFetch<TripOrder>(`/api/v1/trip-orders/${orderId}/assign`, {
    method: "POST",
    body: JSON.stringify({
      assigned_vehicle_id: vehicleId,
      assigned_driver_id: driverId,
    }),
  });
}
