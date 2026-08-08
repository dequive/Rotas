"use client";

import { bffFetch } from "./bff";
import type {
  Item,
  StockMovementIn,
  StockMovementOut,
  StockMovementResponse,
} from "./inventory-api";

export function createItem(data: {
  name: string;
  sku?: string;
  description?: string;
  unit_of_measure?: string;
}): Promise<Item> {
  return bffFetch<Item>("/api/v1/inventory/items", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function registerStockIn(data: StockMovementIn): Promise<StockMovementResponse> {
  return bffFetch<StockMovementResponse>("/api/v1/inventory/movements/in", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function registerStockOut(data: StockMovementOut): Promise<StockMovementResponse> {
  return bffFetch<StockMovementResponse>("/api/v1/inventory/movements/out", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
