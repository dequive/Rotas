import { apiFetch } from "./api";

export interface ClientResponse {
  id: string;
  tenant_id: string;
  trading_name: string;
  legal_name: string | null;
  nuit: string;
  address: string | null;
  city: string | null;
  phone: string | null;
  email: string | null;
  payment_terms_days: number;
  credit_limit: string | number | null; // Decimal from backend
  outstanding_balance: string | number;  // Decimal from backend
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateClientPayload {
  trading_name: string;
  legal_name?: string;
  nuit: string;
  address?: string;
  city?: string;
  phone?: string;
  email?: string;
  payment_terms_days: number;
  credit_limit?: number;
}

export async function loadClients(): Promise<ClientResponse[]> {
  try {
    return await apiFetch<ClientResponse[]>("/api/v1/clients?limit=200", { revalidate: 30 });
  } catch {
    return [];
  }
}
