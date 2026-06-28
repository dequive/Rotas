export interface BillableTrip {
  id: string;
  contract_id: string | null;
  client_name: string;
  contract_reference: string | null;
  origin: string;
  destination: string;
  actual_revenue: string;
  billing_status: string;
  billed_at: string | null;
}

export async function fetchBillableTrips(
  periodStart?: string,
  periodEnd?: string
): Promise<BillableTrip[]> {
  const params = new URLSearchParams();
  if (periodStart) params.append("period_start", periodStart);
  if (periodEnd) params.append("period_end", periodEnd);

  const url = `/api/billing/billable-trips${params.toString() ? '?' + params.toString() : ''}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Failed to fetch billable trips");
  }
  const data = await response.json();
  return data.items || [];
}

export async function createBillingDocument(payload: {
  contract_id: string | null;
  client_name: string;
  contract_reference: string | null;
  billing_period_start: string;
  billing_period_end: string;
  currency: string;
  trip_ids: string[];
  client_nuit: string | null;
}): Promise<any> {
  const response = await fetch("/api/billing/documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("Failed to create billing document");
  }
  return await response.json();
}
