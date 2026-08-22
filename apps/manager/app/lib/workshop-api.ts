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
  status:
    | "draft"
    | "approved"
    | "open"
    | "in_progress"
    | "quality_check"
    | "closed"
    | "cancelled";
  billing_status?: string;
  billing_document_id?: string | null;
  billing_error?: string | null;
  closed_at?: string | null;
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
  billing_status?: string;
  billing_document_id?: string | null;
  billing_error?: string | null;
  closed_at?: string | null;
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
      billing_status: item.billing_status,
      billing_document_id: item.billing_document_id,
      billing_error: item.billing_error,
      closed_at: item.closed_at,
      created_at: item.created_at,
      updated_at: item.updated_at,
    }));
    return { data, truncated: raw.length === PAGE_LIMIT, error: null };
  } catch (err) {
    return { data: [], truncated: false, error: err instanceof Error ? err.message : "Erro ao carregar ordens de trabalho." };
  }
}

export interface WorkOrderLaborSession {
  id: string;
  user_id: string;
  mechanic_name: string;
  started_at: string | null;
  completed_at: string;
  minutes_worked: number;
  hourly_rate_applied: number;
  total_labor_cost: number;
  voided_at: string | null;
  void_reason: string | null;
}

export interface WorkOrderDetail {
  work_order: {
    id: string;
    work_order_number: string;
    status: string;
    diagnosis: string | null;
    planned_work: string;
    estimated_cost: number | null;
    actual_cost: number | null;
    origin_type: string;
    billing_status: string;
    billing_error: string | null;
    document_id: string | null;
    invoice_number: string | null;
    invoice_status: string | null;
    approved_at?: string | null;
    quality_checked_at?: string | null;
    quality_notes: string | null;
    closed_at?: string | null;
    close_notes?: string | null;
    created_at: string;
    updated_at: string;
  };
  vehicle: {
    id: string;
    plate: string;
    brand: string | null;
    model: string | null;
    current_km: number;
    odometer_at_reception: number | null;
  } | null;
  client: {
    id: string | null;
    trading_name: string;
    legal_name: string | null;
    client_type: string;
    nuit: string | null;
    is_fleet_owned: boolean;
  };
  reception: {
    id: string;
    reception_number: string;
    reported_issues: string | null;
    client_signature_file_id: string | null;
    photos: Array<{
      id: string;
      file_id: string;
      caption: string | null;
      taken_at: string;
      download_path: string;
    }>;
  } | null;
  quote: {
    id: string;
    quote_number: string;
    status: string;
    approved_value: number;
    client_signature_file_id: string | null;
    evidence_photo_file_id: string | null;
  } | null;
  tasks: Array<{
    id: string;
    description: string;
    status: string;
    assigned_to: string | null;
    assigned_mechanic_name: string | null;
    estimated_minutes: number | null;
    actual_minutes: number | null;
    labor_sessions: WorkOrderLaborSession[];
  }>;
  parts_issued: Array<{
    inventory_id: string;
    sku: string;
    name: string;
    unit: string;
    issued_quantity: number;
    returned_quantity: number;
    net_quantity: number;
    net_cost: number;
  }>;
  unreturned_tools: Array<{
    checkout_id: string;
    tool_id: string;
    code: string;
    name: string;
    checked_out_at: string;
  }>;
  blockers: { incomplete_tasks: number; unreturned_tools: number };
}

export interface WorkOrderProfitability {
  work_order_id: string;
  work_order_number: string;
  total_revenue: number;
  total_labor_minutes: number;
  total_labor_cost: number;
  total_parts_cost: number;
  total_cost: number;
  gross_profit_mzn: number;
  gross_profit_margin_percent: number;
  is_profitable: boolean;
}

export async function loadWorkOrderDetail(workOrderId: string): Promise<WorkOrderDetail> {
  return apiFetch<WorkOrderDetail>(`/api/v1/workshop/work-orders/${workOrderId}`, {
    revalidate: 0,
  });
}

export async function loadWorkOrderProfitability(
  workOrderId: string,
): Promise<WorkOrderProfitability> {
  return apiFetch<WorkOrderProfitability>(
    `/api/v1/workshop/work-orders/${workOrderId}/profitability`,
    { revalidate: 0 },
  );
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

// ─────────────────────────────────────────────────────────────────────────────
// Inventory (Spare Parts) API
// ─────────────────────────────────────────────────────────────────────────────

export interface SparePartInventory {
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
}

export interface SparePartReceiptCreate {
  inventory_id: string;
  request_reference: string;
  quantity: number;
  unit_cost: number;
  occurred_at: string;
  notes?: string;
}

export async function loadSpareParts(): Promise<SparePartInventory[]> {
  try {
    return await apiFetch<SparePartInventory[]>("/api/v1/workshop/spare-parts", { revalidate: 0 });
  } catch (err) {
    console.error("Erro ao carregar peças", err);
    return [];
  }
}

export async function createSparePart(payload: { sku: string; name: string; unit: string; minimum_quantity: number }) {
  return apiFetch("/api/v1/workshop/spare-parts", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function recordSparePartReceipt(partId: string, payload: SparePartReceiptCreate) {
  return apiFetch(`/api/v1/workshop/spare-parts/${partId}/movements`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Profitability & BI Summary API
// ─────────────────────────────────────────────────────────────────────────────

export interface ProfitabilitySummaryItem {
  work_order_id: string;
  work_order_number: string;
  status: string;
  created_at: string;
  client_name: string;
  vehicle_name: string;
  confirmed_revenue: number;
  projected_revenue: number;
  effective_revenue: number;
  total_labor_cost: number;
  total_parts_cost: number;
  total_cost: number;
  margin_mzn: number;
  margin_pct: number;
  is_profitable: boolean;
}

export interface WorkshopProfitabilitySummary {
  summary: {
    confirmed_revenue: number;
    projected_revenue: number;
    total_labor_cost: number;
    total_parts_cost: number;
    total_cost: number;
    confirmed_gross_profit: number;
    confirmed_gross_margin_pct: number;
    negative_margin_count: number;
    total_work_orders: number;
  };
  work_orders: ProfitabilitySummaryItem[];
}

export async function getWorkshopProfitabilitySummary(params?: {
  start_date?: string;
  end_date?: string;
  client_id?: string;
  vehicle_id?: string;
  status?: string;
}): Promise<WorkshopProfitabilitySummary | null> {
  try {
    const qs = new URLSearchParams();
    if (params?.start_date) qs.set("start_date", params.start_date);
    if (params?.end_date) qs.set("end_date", params.end_date);
    if (params?.client_id) qs.set("client_id", params.client_id);
    if (params?.vehicle_id) qs.set("vehicle_id", params.vehicle_id);
    if (params?.status) qs.set("status", params.status);
    const queryStr = qs.toString() ? `?${qs.toString()}` : "";
    return await apiFetch<WorkshopProfitabilitySummary>(`/api/v1/workshop/profitability/summary${queryStr}`, { revalidate: 0 });
  } catch (err) {
    console.error("Erro ao carregar sumário de rentabilidade:", err);
    return null;
  }
}

export interface WorkshopQuoteItem {
  id: string;
  item_type: "labor" | "part";
  description: string;
  part_id?: string | null;
  quantity: number;
  unit_price: number;
  warranty_months: number;
  warranty_km: number;
}

export interface WorkshopQuote {
  id: string;
  quote_number: string;
  vehicle_id: string;
  vehicle_plate?: string;
  client_id?: string | null;
  client_name?: string;
  reception_id?: string | null;
  related_work_order_id?: string | null;
  status: "draft" | "sent" | "accepted" | "rejected" | "converted" | "expired";
  is_supplemental: boolean;
  valid_until?: string | null;
  labor_total: number;
  parts_total: number;
  total_amount: number;
  tax_total: number;
  notes?: string | null;
  accepted_at?: string | null;
  rejected_at?: string | null;
  acceptance_channel?: string | null;
  accepted_by_person_name?: string | null;
  client_signature_file_id?: string | null;
  evidence_photo_file_id?: string | null;
  created_at: string;
  updated_at?: string;
  items?: WorkshopQuoteItem[];
}

interface ApiWorkshopQuote extends Omit<
  WorkshopQuote,
  "labor_total" | "parts_total" | "total_amount" | "tax_total" | "items"
> {
  labor_total: string | number;
  parts_total: string | number;
  total_amount: string | number;
  tax_total: string | number;
  items?: Array<Omit<WorkshopQuoteItem, "quantity" | "unit_price"> & {
    quantity: string | number;
    unit_price: string | number;
  }>;
}

export interface QuotesResult {
  data: WorkshopQuote[];
  truncated: boolean;
  error: string | null;
}

function mapQuote(item: ApiWorkshopQuote): WorkshopQuote {
  return {
    ...item,
    labor_total: parseAmount(item.labor_total) ?? 0,
    parts_total: parseAmount(item.parts_total) ?? 0,
    total_amount: parseAmount(item.total_amount) ?? 0,
    tax_total: parseAmount(item.tax_total) ?? 0,
    items: item.items?.map((quoteItem) => ({
      ...quoteItem,
      quantity: parseAmount(quoteItem.quantity) ?? 0,
      unit_price: parseAmount(quoteItem.unit_price) ?? 0,
    })),
  };
}

export async function loadQuotesResult(): Promise<QuotesResult> {
  try {
    const raw = await apiFetch<ApiWorkshopQuote[]>("/api/v1/workshop/quotes?limit=200", {
      revalidate: 0,
    });
    return {
      data: raw.map(mapQuote),
      truncated: raw.length === 200,
      error: null,
    };
  } catch (err) {
    return {
      data: [],
      truncated: false,
      error: err instanceof Error ? err.message : "Erro ao carregar orçamentos da oficina.",
    };
  }
}

export async function loadQuotes(): Promise<WorkshopQuote[]> {
  return (await loadQuotesResult()).data;
}

export interface ReceptionPhoto {
  id: string;
  tenant_id: string;
  reception_id: string;
  file_id: string;
  caption: string | null;
  taken_at: string;
  created_at: string;
}

export interface VehicleReception {
  id: string;
  tenant_id: string;
  vehicle_id: string;
  client_id: string | null;
  reception_number: string;
  received_by: string;
  received_at: string;
  odometer_at_reception: number;
  reported_issues: string | null;
  visual_condition: string | null;
  personal_items: string | null;
  fuel_level: string;
  delivered_by_name: string | null;
  delivered_by_phone: string | null;
  pickup_authorized_by_name: string | null;
  pickup_authorized_by_phone: string | null;
  client_signature_file_id: string | null;
  estimated_completion_at: string | null;
  status: "received" | "in_service" | "ready" | "delivered" | "returned_no_service";
  photos: ReceptionPhoto[];
  created_at: string;
  updated_at: string;
}

export interface ReceptionsResult {
  data: VehicleReception[];
  truncated: boolean;
  error: string | null;
}

export async function loadReceptions(status?: string): Promise<ReceptionsResult> {
  try {
    const qs = new URLSearchParams({ limit: "200" });
    if (status) qs.set("status", status);
    const data = await apiFetch<VehicleReception[]>(
      `/api/v1/workshop/receptions?${qs}`,
      { revalidate: 10 },
    );
    return { data, truncated: data.length === 200, error: null };
  } catch (err) {
    return {
      data: [],
      truncated: false,
      error: err instanceof Error ? err.message : "Erro ao carregar receções da oficina.",
    };
  }
}

export interface ReceptionDetailResult {
  data: VehicleReception | null;
  error: string | null;
}

export async function loadReceptionDetailResult(
  receptionId: string,
): Promise<ReceptionDetailResult> {
  try {
    const data = await apiFetch<VehicleReception>(
      `/api/v1/workshop/receptions/${receptionId}`,
      { revalidate: 0 },
    );
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : "Erro ao carregar a receção.",
    };
  }
}

export interface ServiceWarranty {
  id: string;
  tenant_id: string;
  work_order_id: string;
  vehicle_id: string;
  client_id: string | null;
  warranty_type: "parts" | "labor" | "full_service";
  duration_months: number;
  duration_km: number | null;
  starts_at: string;
  expires_at: string;
  km_at_service: number;
  status: string;
  notes: string | null;
  created_at: string;
}

export interface WarrantiesResult {
  data: ServiceWarranty[];
  truncated: boolean;
  error: string | null;
}

export async function loadWarrantiesResult(status?: string): Promise<WarrantiesResult> {
  try {
    const qs = new URLSearchParams({ limit: "200" });
    if (status) qs.set("status", status);
    const data = await apiFetch<ServiceWarranty[]>(
      `/api/v1/workshop/warranties?${qs}`,
      { revalidate: 10 },
    );
    return { data, truncated: data.length === 200, error: null };
  } catch (err) {
    return {
      data: [],
      truncated: false,
      error: err instanceof Error ? err.message : "Erro ao carregar garantias da oficina.",
    };
  }
}
