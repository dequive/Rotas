import { apiFetch } from "./api";

export interface WorkOrder {
  id: string;
  work_order_number: string;
  vehicle_id: string;
  vehicle_plate?: string; // Optional resolved plate
  diagnosis: string | null;
  planned_work: string;
  estimated_cost: number | null;
  actual_cost: number | null;
  status: "draft" | "open" | "in_progress" | "quality_check" | "closed";
  created_at: string;
  updated_at: string;
}

export interface MaintenanceRequest {
  id: string;
  vehicle_id: string;
  vehicle_plate?: string;
  request_type: string;
  priority: "low" | "normal" | "high" | "critical";
  description: string;
  odometer_reading: number | null;
  status: "open" | "approved" | "rejected" | "cancelled";
  requested_at: string;
}

export interface ImminentMaintenanceAlert {
  plan_id: string;
  plan_name: string;
  vehicle_id: string;
  vehicle_plate: string;
  next_due_at: string | null;
  next_due_km: number | null;
  current_km: number | null;
  trigger_type: "calendar" | "odometer" | "overdue";
}

interface ApiWorkOrder {
  id: string;
  vehicle_id: string;
  work_order_number: string;
  diagnosis: string | null;
  planned_work: string;
  estimated_cost: string | number | null;
  actual_cost: string | number | null;
  status: string;
  created_at: string;
  updated_at: string;
}

interface ApiMaintenanceRequest {
  id: string;
  vehicle_id: string;
  request_type: string;
  priority: string;
  description: string;
  odometer_reading: number | null;
  status: string;
  requested_at: string;
}

function parseAmount(value: string | number | null): number | null {
  if (value === null) return null;
  const num = typeof value === "number" ? value : Number(value);
  return Number.isFinite(num) ? num : null;
}

export async function loadWorkOrders(status?: string): Promise<WorkOrder[]> {
  const url = status
    ? `/api/v1/workshop/work-orders?status=${status}&limit=500`
    : "/api/v1/workshop/work-orders?limit=500";
  const data = await apiFetch<ApiWorkOrder[]>(url, { revalidate: 10 });
  return data.map((item) => ({
    id: item.id,
    work_order_number: item.work_order_number,
    vehicle_id: item.vehicle_id,
    diagnosis: item.diagnosis,
    planned_work: item.planned_work,
    estimated_cost: parseAmount(item.estimated_cost),
    actual_cost: parseAmount(item.actual_cost),
    status: item.status as WorkOrder["status"],
    created_at: item.created_at,
    updated_at: item.updated_at,
  }));
}

export async function loadMaintenanceRequests(status?: string): Promise<MaintenanceRequest[]> {
  const url = status
    ? `/api/v1/workshop/maintenance-requests?status=${status}&limit=500`
    : "/api/v1/workshop/maintenance-requests?limit=500";
  const data = await apiFetch<ApiMaintenanceRequest[]>(url, { revalidate: 10 });
  return data.map((item) => ({
    id: item.id,
    vehicle_id: item.vehicle_id,
    request_type: item.request_type,
    priority: item.priority as MaintenanceRequest["priority"],
    description: item.description,
    odometer_reading: item.odometer_reading,
    status: item.status as MaintenanceRequest["status"],
    requested_at: item.requested_at,
  }));
}
