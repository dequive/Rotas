import { apiFetch } from "./api";

export interface Contract {
  id: string;
  client_name: string;
  contract_reference: string;
  title: string;
  status: string;
  service_type: string;
  billing_cycle: string;
  billing_basis: string;
  currency: string;
  default_unit_price: number | null;
  requires_load_permit: boolean;
  requires_delivery_proof: boolean;
  starts_at: string | null;
  ends_at: string | null;
}

export interface CreateContractPayload {
  client_name: string;
  contract_reference: string;
  title: string;
  service_type: string;
  billing_cycle: string;
  billing_basis: string;
  currency: string;
  default_unit_price?: number;
  requires_load_permit?: boolean;
  requires_delivery_proof?: boolean;
  requires_cargo_manifest_for_manufactured_goods?: boolean;
  starts_at?: string;
  ends_at?: string;
  notes?: string;
}

export async function loadContracts(): Promise<Contract[]> {
  try {
    return await apiFetch<Contract[]>("/api/v1/contracts/?limit=200", { revalidate: 30 });
  } catch {
    return [];
  }
}

async function createContract(payload: CreateContractPayload): Promise<Contract> {
  return apiFetch<Contract>("/api/v1/contracts/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function updateContract(id: string, payload: Partial<CreateContractPayload>): Promise<Contract> {
  return apiFetch<Contract>(`/api/v1/contracts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
