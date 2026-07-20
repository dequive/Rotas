import { apiFetch } from "./api";

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
  return apiFetch<Warehouse[]>("/api/v1/inventory/warehouses", { revalidate: 15 });
}

export async function fetchItems(): Promise<Item[]> {
  return apiFetch<Item[]>("/api/v1/inventory/items", { revalidate: 15 });
}

export async function createWarehouse(data: { name: string; location?: string }): Promise<Warehouse> {
  return apiFetch<Warehouse>("/api/v1/inventory/warehouses", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function createItem(data: { name: string; sku?: string; description?: string; unit_of_measure?: string }): Promise<Item> {
  return apiFetch<Item>("/api/v1/inventory/items", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function registerStockIn(data: StockMovementIn): Promise<StockMovementResponse> {
  return apiFetch<StockMovementResponse>("/api/v1/inventory/movements/in", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function registerStockOut(data: StockMovementOut): Promise<StockMovementResponse> {
  return apiFetch<StockMovementResponse>("/api/v1/inventory/movements/out", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
