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

const PAGE_LIMIT = 500;

export interface WorkOrdersResult {
  data: WorkOrder[];
  truncated: boolean;
  error: string | null;
}

export async function loadWorkOrders(status?: string): Promise<WorkOrdersResult> {
  try {
    const qs = new URLSearchParams({ limit: String(PAGE_LIMIT) });
    if (status) qs.set("status", status);
    const raw = await apiFetch<ApiWorkOrder[]>(`/api/v1/workshop/work-orders?${qs}`, { revalidate: 10 });
    const data = raw.map((item) => ({
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
    return { data, truncated: raw.length === PAGE_LIMIT, error: null };
  } catch (err) {
    return { data: [], truncated: false, error: err instanceof Error ? err.message : "Erro ao carregar ordens de trabalho." };
  }
}

export async function loadMaintenanceRequests(status?: string): Promise<MaintenanceRequest[]> {
  try {
    const qs = new URLSearchParams({ limit: String(PAGE_LIMIT) });
    if (status) qs.set("status", status);
    return (await apiFetch<ApiMaintenanceRequest[]>(`/api/v1/workshop/maintenance-requests?${qs}`, { revalidate: 10 })).map((item) => ({
      id: item.id,
      vehicle_id: item.vehicle_id,
      request_type: item.request_type,
      priority: item.priority as MaintenanceRequest["priority"],
      description: item.description,
      odometer_reading: item.odometer_reading,
      status: item.status as MaintenanceRequest["status"],
      requested_at: item.requested_at,
    }));
  } catch {
    return [];
  }
}

// ── Spare Parts Inventory ────────────────────────────────────────────────────

export interface SparePart {
  id: string;
  sku: string;
  name: string;
  unit: string;
  current_quantity: number;
  minimum_quantity: number;
  average_unit_cost: number;
  status: string;
  category: string | null;
  shelf_location: string | null;
  supplier_name: string | null;
  lead_time_days: number | null;
  reorder_quantity: number | null;
}

export interface LowStockItem {
  id: string;
  sku: string;
  name: string;
  current_quantity: string;
  minimum_quantity: string;
  reorder_quantity: number | null;
  supplier_name: string | null;
  lead_time_days: number | null;
}

export interface LowStockResponse {
  items: LowStockItem[];
  total: number;
}

export async function loadSparePartsInventory(): Promise<SparePart[]> {
  try {
    return await apiFetch<SparePart[]>("/api/v1/workshop/spare-parts?limit=500", { revalidate: 30 });
  } catch {
    return [];
  }
}

export async function loadLowStockParts(): Promise<LowStockResponse> {
  try {
    return await apiFetch<LowStockResponse>("/api/v1/workshop/spare-parts/low-stock", { revalidate: 30 });
  } catch {
    return { items: [], total: 0 };
  }
}

// ── Tools ────────────────────────────────────────────────────────────────────

export interface WorkshopToolItem {
  id: string;
  code: string;
  name: string;
  status: string;
  is_critical: boolean;
  calibration_due_at: string | null;
  category: string | null;
  location: string | null;
  serial_number: string | null;
}

export interface ToolCalibrationEvent {
  id: string;
  tool_id: string;
  calibrated_by: string | null;
  calibrated_at: string;
  next_due_at: string;
  notes: string | null;
  created_at: string;
}

export async function loadTools(): Promise<WorkshopToolItem[]> {
  try {
    return await apiFetch<WorkshopToolItem[]>("/api/v1/workshop/tools?limit=500", { revalidate: 30 });
  } catch {
    return [];
  }
}

export async function loadToolCalibrationHistory(toolId: string): Promise<ToolCalibrationEvent[]> {
  try {
    return await apiFetch<ToolCalibrationEvent[]>(`/api/v1/workshop/tools/${toolId}/calibration-history`, { revalidate: 30 });
  } catch {
    return [];
  }
}

// ── Vehicle History ──────────────────────────────────────────────────────────

export interface VehicleHistoryEvent {
  event_type: string;
  event_date: string;
  title: string;
  description: string | null;
  reference_id: string;
  odometer_reading: number | null;
}

export interface VehicleHistoryResponse {
  events: VehicleHistoryEvent[];
  next_cursor: string | null;
  total_count: number;
}

export interface VehicleHistoryParams {
  from?: string;
  to?: string;
  types?: string;
  cursor?: string;
  limit?: number;
}

export async function loadVehicleHistory(
  vehicleId: string,
  params?: VehicleHistoryParams
): Promise<VehicleHistoryResponse> {
  try {
    const qs = new URLSearchParams();
    if (params?.from) qs.set("from", params.from);
    if (params?.to) qs.set("to", params.to);
    if (params?.types) qs.set("types", params.types);
    if (params?.cursor) qs.set("cursor", params.cursor);
    if (params?.limit) qs.set("limit", String(params.limit));
    const query = qs.toString() ? `?${qs}` : "";
    return await apiFetch<VehicleHistoryResponse>(`/api/v1/vehicles/${vehicleId}/history${query}`, { revalidate: 10 });
  } catch {
    return { events: [], next_cursor: null, total_count: 0 };
  }
}
