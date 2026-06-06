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
  client: string;
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
  billing_period_start: string;
  billing_period_end: string;
  total_amount: number | string | null;
  status: string;
  item_count: number;
}

export interface BillingTripLoadResult {
  trips: BillingTrip[];
  source: "api" | "fallback";
  message: string | null;
}

const fallbackTrips: BillingTrip[] = [
  {
    id: "TRP-001",
    deliveryProofId: null,
    contractId: null,
    plate: "MPT-00-RT",
    client: null,
    contractReference: null,
    route: "Matola -> Beira",
    loadState: "Carregado/Vazio",
    cargo: "Cimento ensacado",
    deliveredAt: "2026-06-03",
    deliveryProof: "GD-001 validada",
    status: "uncontracted",
    amount: null,
  },
  {
    id: "TRP-002",
    deliveryProofId: null,
    contractId: null,
    plate: "ABC-123-MZ",
    client: "Cliente Industrial Piloto",
    contractReference: "CTR-PILOTO-001",
    route: "Beira -> Nacala",
    loadState: "Carregado/Carregado",
    cargo: "Produtos manufaturados",
    deliveredAt: "2026-06-05",
    deliveryProof: "GD-002 em revisao",
    status: "pending_delivery_validation",
    amount: 18000,
  },
  {
    id: "TRP-003",
    deliveryProofId: null,
    contractId: null,
    plate: "ADF-987-MZ",
    client: "Cliente Industrial Piloto",
    contractReference: "CTR-PILOTO-001",
    route: "Maputo -> Chimoio",
    loadState: "Carregado/Vazio",
    cargo: "Material de construcao",
    deliveredAt: "2026-06-07",
    deliveryProof: "GD-003 validada",
    status: "billing_draft",
    amount: 12500,
  },
  {
    id: "TRP-004",
    deliveryProofId: null,
    contractId: null,
    plate: "MPT-442-MZ",
    client: "Distribuidora Norte",
    contractReference: "CTR-NORTE-004",
    route: "Nacala -> Nampula",
    loadState: "Vazio/Carregado",
    cargo: "Bebidas",
    deliveredAt: "2026-06-08",
    deliveryProof: "GD-004 validada",
    status: "billed",
    amount: 9500,
  },
];

const fallbackDocuments: BillingDocumentSummary[] = [
  {
    id: "fallback-doc-001",
    reference: "BIL-2026-06-001",
    client: "Cliente Industrial Piloto",
    period: "Junho 2026",
    trips: 4,
    amount: 68000,
    status: "Rascunho",
  },
  {
    id: "fallback-doc-002",
    reference: "BIL-2026-06-002",
    client: "Distribuidora Norte",
    period: "Junho 2026",
    trips: 2,
    amount: 19000,
    status: "Emitido",
  },
];

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
  return {
    apiBaseUrl: process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000",
    tenantId: process.env.ROTAS_TENANT_ID ?? null,
    token: process.env.ROTAS_MANAGER_TOKEN ?? "test-token",
  };
}

export async function loadBillingTrips(): Promise<BillingTripLoadResult> {
  try {
    const payload = await apiFetch<ApiBillableTrip[]>("/api/v1/billing/billable-trips?limit=200", { revalidate: 15 });
    return { trips: payload.map(mapTrip), source: "api", message: null };
  } catch (error) {
    return {
      trips: fallbackTrips,
      source: "fallback",
      message: error instanceof Error ? `Billing: ${error.message}` : "Indisponível.",
    };
  }
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
  try {
    const payload = await apiFetch<ApiBillingDocument[]>("/api/v1/billing/documents?limit=20", { revalidate: 15 });
    return payload.map((document) => ({
      id: document.id,
      reference: document.contract_reference
        ? `BIL-${document.contract_reference}-${document.id.slice(0, 8)}`
        : `BIL-${document.id.slice(0, 8)}`,
      client: document.client_name,
      period: formatPeriod(document.billing_period_start),
      trips: document.item_count,
      amount: parseAmount(document.total_amount),
      status: mapDocumentStatus(document.status),
    }));
  } catch {
    return fallbackDocuments;
  }
}
