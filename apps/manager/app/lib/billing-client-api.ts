"use client";

import { bffRequest } from "./bff";
import type {
  BillingStatus,
  BillingTrip,
  ClientPayment,
  ClientPaymentPayload,
} from "./billing-api";

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

async function jsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string;
      error?: { message?: string; code?: string };
    };
    throw new Error(
      body.error?.message ?? body.error?.code ?? body.detail ?? `HTTP ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

function mapTrip(item: ApiBillableTrip): BillingTrip {
  const validStatuses: BillingStatus[] = [
    "pending_delivery_proof",
    "pending_delivery_validation",
    "uncontracted",
    "billable",
    "billing_draft",
    "billed",
  ];
  const statusValue = item.candidate_status || item.billing_status;
  const amount = item.amount === null ? null : Number(item.amount);
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
    deliveredAt: item.delivered_at?.slice(0, 10) ?? "-",
    deliveryProof: item.delivery_proof_status
      ? `Descarga ${item.delivery_proof_status}`
      : "Sem prova de descarga",
    status: validStatuses.includes(statusValue as BillingStatus)
      ? (statusValue as BillingStatus)
      : "pending_delivery_validation",
    amount: amount !== null && Number.isFinite(amount) ? amount : null,
  };
}

export async function loadBillingTrips(): Promise<{ trips: BillingTrip[]; source: "api"; message: null }> {
  const response = await bffRequest("/api/v1/billing/billable-trips?limit=200");
  const payload = await jsonOrThrow<ApiBillableTrip[]>(response);
  return { trips: payload.map(mapTrip), source: "api", message: null };
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
  await jsonOrThrow(
    await bffRequest("/api/v1/billing/documents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export async function createBillingWaiver(tripId: string, reason: string) {
  return jsonOrThrow<{ id: string; status: string }>(
    await bffRequest("/api/v1/billing/waivers", {
      method: "POST",
      body: JSON.stringify({ trip_id: tripId, reason }),
    }),
  );
}

export async function approveBillingWaiver(waiverId: string) {
  return jsonOrThrow<{ id: string; status: string }>(
    await bffRequest(`/api/v1/billing/waivers/${waiverId}/approve`, { method: "POST" }),
  );
}

export async function rejectBillingWaiver(waiverId: string) {
  return jsonOrThrow<{ id: string; status: string }>(
    await bffRequest(`/api/v1/billing/waivers/${waiverId}/reject`, { method: "POST" }),
  );
}

export async function enqueueExportJob(documentId: string, format: "pdf" | "xlsx") {
  return jsonOrThrow<{ jobId: string; status: string }>(
    await bffRequest(
      `/api/v1/billing/documents/${documentId}/export-job?export_format=${format}`,
      { method: "POST" },
    ),
  );
}

export async function getJobStatus(jobId: string) {
  return jsonOrThrow<{
    status: "queued" | "processing" | "done" | "failed";
    fileUrl?: string;
  }>(await bffRequest(`/api/v1/billing/jobs/${jobId}/status`));
}

export function getJobDownloadUrl(jobId: string): string {
  return `/api/proxy?path=${encodeURIComponent(`/api/v1/billing/jobs/${jobId}/download`)}`;
}

export async function registerPayment(
  payload: ClientPaymentPayload,
  idempotencyKey: string,
): Promise<ClientPayment> {
  return jsonOrThrow<ClientPayment>(
    await bffRequest("", {
      path: "/api/payments",
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
    }),
  );
}
