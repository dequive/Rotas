import { getAuthToken } from "./auth";
import { API_BASE_URL } from "./api";

export interface Warehouse {
  id: string;
  tenant_id: string;
  name: string;
  location: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Item {
  id: string;
  tenant_id: string;
  category_id: string | null;
  sku: string | null;
  name: string;
  description: string | null;
  unit_of_measure: string;
  current_stock: number;
  average_unit_cost: number;
  created_at: string;
  updated_at: string;
}

export interface StockMovementIn {
  item_id: string;
  warehouse_id: string;
  quantity: number;
  unit_cost: number;
  reference_doc?: string;
  notes?: string;
}

export interface StockMovementOut {
  item_id: string;
  warehouse_id: string;
  quantity: number;
  reference_doc?: string;
  notes?: string;
}

export interface StockMovementResponse {
  id: string;
  tenant_id: string;
  item_id: string;
  warehouse_id: string;
  movement_type: "inbound" | "outbound" | "adjustment";
  quantity: number;
  unit_cost: number;
  total_value: number;
  reference_doc: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
}

export async function fetchWarehouses(): Promise<Warehouse[]> {
  const token = await getAuthToken();
  const res = await fetch(`${API_BASE_URL}/inventory/warehouses`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch warehouses");
  return res.json();
}

export async function fetchItems(): Promise<Item[]> {
  const token = await getAuthToken();
  const res = await fetch(`${API_BASE_URL}/inventory/items`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch items");
  return res.json();
}

export async function createWarehouse(data: { name: string; location?: string }): Promise<Warehouse> {
  const token = await getAuthToken();
  const res = await fetch(`${API_BASE_URL}/inventory/warehouses`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create warehouse");
  return res.json();
}

export async function createItem(data: { name: string; sku?: string; description?: string; unit_of_measure?: string }): Promise<Item> {
  const token = await getAuthToken();
  const res = await fetch(`${API_BASE_URL}/inventory/items`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create item");
  return res.json();
}

export async function registerStockIn(data: StockMovementIn): Promise<StockMovementResponse> {
  const token = await getAuthToken();
  const res = await fetch(`${API_BASE_URL}/inventory/movements/in`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to register stock IN");
  return res.json();
}

export async function registerStockOut(data: StockMovementOut): Promise<StockMovementResponse> {
  const token = await getAuthToken();
  const res = await fetch(`${API_BASE_URL}/inventory/movements/out`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to register stock OUT");
  return res.json();
}
