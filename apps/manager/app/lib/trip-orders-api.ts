import { apiFetch } from "./api";

export interface TripOrder {
  id: string;
  order_number: string | null;
  customer_id: string;
  customer_name: string | null;
  origin: string;
  destination: string;
  cargo_type: string | null;
  cargo_weight_kg: number | null;
  status: string; // 'draft', 'confirmed', 'planning', 'assigned', 'execution', 'completed', 'cancelled'
  planned_dispatch_date: string | null;
  created_at: string;
}

export async function loadPendingTripOrders(): Promise<TripOrder[]> {
  try {
    // Fetch trip orders that need dispatching (e.g. status in 'confirmed', 'planning')
    const qs = "?status=planning&limit=50";
    return await apiFetch<TripOrder[]>(`/api/v1/trip-orders${qs}`, { revalidate: 10 });
  } catch {
    return [];
  }
}

export async function assignTripOrder(orderId: string, vehicleId: string, driverId: string): Promise<TripOrder> {
  return apiFetch<TripOrder>(`/api/v1/trip-orders/${orderId}/assign`, {
    method: "POST",
    body: JSON.stringify({ assigned_vehicle_id: vehicleId, assigned_driver_id: driverId }),
  });
}
