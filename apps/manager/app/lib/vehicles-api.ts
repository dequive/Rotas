import { apiFetch } from "./api";

export interface Vehicle {
  id: string;
  plate: string;
  brand: string;
  model: string;
  year: number;
  category: string;
  status: string;
  current_km: number;
  fuel_type: string;
  color: string | null;
  avg_consumption_target: number | null;
  fuel_limit_daily: number | null;
  documents: Record<string, { number: string; valid_until: string | null }> | null;
}

export interface CreateVehiclePayload {
  plate: string;
  chassis: string;
  brand: string;
  model: string;
  year: number;
  category: string;
  fuel_type: string;
  color?: string;
  current_km: number;
  avg_consumption_target?: number;
  fuel_limit_daily?: number;
}

export async function loadVehicles(): Promise<Vehicle[]> {
  try {
    return await apiFetch<Vehicle[]>("/api/v1/vehicles?limit=200", { revalidate: 20 });
  } catch {
    return [];
  }
}

async function createVehicle(payload: CreateVehiclePayload): Promise<Vehicle> {
  return apiFetch<Vehicle>("/api/v1/vehicles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function updateVehicle(id: string, payload: Partial<CreateVehiclePayload>): Promise<Vehicle> {
  return apiFetch<Vehicle>(`/api/v1/vehicles/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

async function getVehicleQrCode(id: string): Promise<{ qr_code_url: string; deep_link: string }> {
  return apiFetch(`/api/v1/vehicles/${id}/qr-code`);
}
