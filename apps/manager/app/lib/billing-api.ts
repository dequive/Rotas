import { apiFetch } from "./api";

export type BillingStatus =
  | "pending_delivery_proof"
  | "pending_delivery_validation"
  | "uncontracted"
  | "billable"
  | "billing_draft"
  | "billed";

export interface BillingTrip {
  id: string;
  deliveryProofId: string | null;
  contractId: string | null;
  plate: string;
  client: string | null;
  contractReference: string | null;
  route: string;
  loadState: string;
  cargo: string;
  deliveredAt: string;
  deliveryProof: string;
  status: BillingStatus;
  amount: number | null;
  waiverStatus?: "pending_approval" | "active" | "rejected" | null;
  waiverReason?: string | null;
  waiverId?: string | null;
  actualMargin?: number | null;
}

interface ApiBillableTrip {
  trip_id: string;
  delivery_proof_id: string | null;
  contract_id: string | null;
  vehicle_plate: string | null;
  client_name: string | null;
  contract_reference: string | null;
  origin: string;
  destination: string;
  cargo_type: string | null;
  load_state: string | null;
  delivered_at: string | null;
  delivery_proof_status: string | null;
  billing_status: string;
  candidate_status: string;
  amount: number | string | null;
}

export interface ContractOption {
  id: string;
  clientName: string;
  contractReference: string;
  title: string;
  defaultUnitPrice: number | null;
}

export interface BillingDocumentSummary {
  id: string;
  reference: string;
  invoiceNumber: string | null;
  client: string;
  clientId: string | null;
  period: string;
  trips: number;
  amount: number | null;
  status: "Rascunho" | "Emitido" | "Pago" | "Outro";
}

interface ApiContract {
  id: string;
  client_name: string;
  contract_reference: string;
  title: string;
  default_unit_price: number | string | null;
}

interface ApiBillingDocument {
  id: string;
  contract_reference: string | null;
  client_name: string;
  client_id?: string | null;
  billing_period_start: string;
  billing_period_end: string;
  total_amount: number | string | null;
  status: string;
  item_count: number;
  invoice_number: string | null;
}

interface ApiBillingDocumentPage {
  items: ApiBillingDocument[];
  total: number;
}

export interface BillingTripLoadResult {
  trips: BillingTrip[];
  source: "api";
  message: string | null;
}

function parseAmount(value: ApiBillableTrip["amount"]) {
  if (value === null) {
    return null;
  }
  const amount = typeof value === "number" ? value : Number(value);
  return Number.isFinite(amount) ? amount : null;
}

function parseStatus(value: string): BillingStatus {
  const validStatuses: BillingStatus[] = [
    "pending_delivery_proof",
    "pending_delivery_validation",
    "uncontracted",
    "billable",
    "billing_draft",
    "billed",
  ];
  return validStatuses.includes(value as BillingStatus)
    ? (value as BillingStatus)
    : "pending_delivery_validation";
}

function formatDate(value: string | null) {
  if (!value) {
    return "-";
  }
  return value.slice(0, 10);
}

function formatPeriod(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat("pt-MZ", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function mapDocumentStatus(value: string): BillingDocumentSummary["status"] {
  if (value === "draft") return "Rascunho";
  if (value === "issued") return "Emitido";
  if (value === "paid") return "Pago";
  return "Outro";
}

function mapTrip(item: ApiBillableTrip): BillingTrip {
  return {
    id: item.trip_id,
    deliveryProofId: item.delivery_proof_id,
    contractId: item.contract_id,
    plate: item.vehicle_plate ?? "-",
    client: item.client_name,
    contractReference: item.contract_reference,
    route: `${item.origin} -> ${item.destination}`,
    loadState: item.load_state ?? "-",
    cargo: item.cargo_type ?? "-",
    deliveredAt: formatDate(item.delivered_at),
    deliveryProof: item.delivery_proof_status
      ? `Descarga ${item.delivery_proof_status}`
      : "Sem prova de descarga",
    status: parseStatus(item.candidate_status || item.billing_status),
    amount: parseAmount(item.amount),
  };
}

export function getApiConfig() {
  // Client actions are always routed through the authenticated BFF.  This
  // value is only a non-secret capability marker retained for legacy props.
  return {
    tenantId: "bff-session",
  };
}

export async function loadBillingTrips(): Promise<BillingTripLoadResult> {
  const payload = await apiFetch<ApiBillableTrip[]>(
    "/api/v1/billing/billable-trips?limit=200",
    { revalidate: 15 },
  );
  return { trips: payload.map(mapTrip), source: "api", message: null };
}

export async function loadContracts(): Promise<ContractOption[]> {
  try {
    const payload = await apiFetch<ApiContract[]>("/api/v1/contracts/?limit=200", { revalidate: 30 });
    return payload.map((contract) => ({
      id: contract.id,
      clientName: contract.client_name,
      contractReference: contract.contract_reference,
      title: contract.title,
      defaultUnitPrice: parseAmount(contract.default_unit_price),
    }));
  } catch {
    return [];
  }
}

export async function loadBillingDocuments(): Promise<BillingDocumentSummary[]> {
  const payload = await apiFetch<ApiBillingDocumentPage>(
    "/api/v1/billing/documents?limit=20",
    { revalidate: 15 },
  );
  return payload.items.map((document) => ({
    id: document.id,
    reference: document.contract_reference
      ? `BIL-${document.contract_reference}-${document.id.slice(0, 8)}`
      : `BIL-${document.id.slice(0, 8)}`,
    invoiceNumber: document.invoice_number ?? null,
    client: document.client_name,
    clientId: document.client_id ?? null,
    period: formatPeriod(document.billing_period_start),
    trips: document.item_count,
    amount: parseAmount(document.total_amount),
    status: mapDocumentStatus(document.status),
  }));
}

// ─── Waiver API functions ───────────────────────────────────────────────────

export async function createBillingWaiver(
  tripId: string,
  reason: string,
): Promise<{ id: string; status: string }> {
  return apiFetch("/api/v1/billing/waivers", {
    method: "POST",
    body: JSON.stringify({ trip_id: tripId, reason }),
  });
}

export async function approveBillingWaiver(
  waiverId: string,
): Promise<{ id: string; status: string }> {
  return apiFetch(`/api/v1/billing/waivers/${waiverId}/approve`, {
    method: "POST",
  });
}

export async function rejectBillingWaiver(
  waiverId: string,
): Promise<{ id: string; status: string }> {
  return apiFetch(`/api/v1/billing/waivers/${waiverId}/reject`, {
    method: "POST",
  });
}

// ─── Export job API functions ────────────────────────────────────────────────

export async function enqueueExportJob(
  documentId: string,
  format: "pdf" | "xlsx",
): Promise<{ jobId: string; status: string }> {
  // export_format is a FastAPI Query param — pass via URL, not request body
  return apiFetch(
    `/api/v1/billing/documents/${documentId}/export-job?export_format=${format}`,
    { method: "POST" },
  );
}

export async function getJobStatus(
  jobId: string,
): Promise<{ status: "queued" | "processing" | "done" | "failed"; fileUrl?: string }> {
  return apiFetch(`/api/v1/billing/jobs/${jobId}/status`);
}

export function getJobDownloadUrl(jobId: string): string {
  return `/api/v1/billing/jobs/${jobId}/download`;
}

// ── Phase 6: Payment Registration ──────────────────────────────────────────

export interface ClientPaymentPayload {
  client_id: string;
  billing_document_id: string | null; // null = advance payment
  amount: string; // Decimal as string to avoid float precision loss
  currency?: string;
  value_date: string; // ISO datetime string
  payment_method: "bank_transfer" | "cheque" | "cash";
  reference?: string | null;
  notes?: string | null;
}

export interface PaymentAllocationSummary {
  id: string;
  billing_document_id: string;
  amount_applied: string;
  created_at: string;
}

export interface ClientPayment {
  id: string;
  client_id: string;
  billing_document_id: string | null;
  amount: string;
  currency: string;
  value_date: string;
  payment_method: string;
  reference: string | null;
  status: "confirmed" | "voided";
  void_reason: string | null;
  created_at: string;
  allocations: PaymentAllocationSummary[];
}

export interface ClientStatement {
  client: {
    id: string;
    trading_name: string;
    nuit: string | null;
    outstanding_balance: string | null;
  };
  documents: Array<{
    id: string;
    invoice_number: string | null;
    billing_period_start: string;
    billing_period_end: string;
    total_amount: string;
    amount_paid: string;
    outstanding_balance: string;
    due_date: string | null;
    status: string;
  }>;
  payments: Array<{
    id: string;
    amount: string;
    value_date: string;
    payment_method: string;
    reference: string | null;
    status: string;
    unallocated: string;
  }>;
  summary: {
    total_invoiced: string;
    total_paid: string;
    total_outstanding: string;
    advance_balance: string;
  };
}

export async function registerPayment(
  payload: ClientPaymentPayload,
  idempotencyKey: string,
): Promise<ClientPayment> {
  const res = await fetch("/api/payments", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { message?: string; detail?: string };
    throw new Error(err?.message ?? err?.detail ?? `Payment registration failed: ${res.status}`);
  }
  return res.json() as Promise<ClientPayment>;
}

export async function voidPayment(
  paymentId: string,
  voidReason: string,
): Promise<ClientPayment> {
  const res = await fetch(`/api/payments/${paymentId}/void`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ void_reason: voidReason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { message?: string; detail?: string };
    throw new Error(err?.message ?? err?.detail ?? `Void failed: ${res.status}`);
  }
  return res.json() as Promise<ClientPayment>;
}

export async function getClientStatement(
  clientId: string,
  options?: { period_start?: string; period_end?: string },
): Promise<ClientStatement> {
  const params = new URLSearchParams();
  if (options?.period_start) params.set("period_start", options.period_start);
  if (options?.period_end) params.set("period_end", options.period_end);
  const query = params.toString() ? `?${params}` : "";
  const res = await fetch(`/api/clients/${clientId}/statement${query}`);
  if (!res.ok) throw new Error(`Statement fetch failed: ${res.status}`);
  return res.json() as Promise<ClientStatement>;
}

export async function createBillingDocument(payload: {
  contract_id: string | null;
  client_nuit: string | null;
  client_name: string;
  contract_reference: string | null;
  billing_period_start: string;
  billing_period_end: string;
  currency: string;
  trip_ids: string[];
}): Promise<void> {
  await apiFetch("/api/v1/billing/documents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
