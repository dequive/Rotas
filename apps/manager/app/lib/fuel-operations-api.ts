import { apiFetch } from "./api";

export interface FuelTank {
  id: string;
  code: string;
  name: string;
  fuelType: string;
  capacityLiters: number;
  minimumStockLiters: number;
  currentStockLiters: number;
  averageUnitCost: number;
  location: string | null;
  status: string;
}

export interface FuelControlBoard {
  summary: { tanks: number; purchasesPending: number; lowStockTanks: number; totalStockLiters: number };
  tanks: FuelTank[];
  queues: { lowStockTanks: FuelTank[] };
}

interface ApiFuelTank {
  id: string;
  code: string;
  name: string;
  fuel_type: string;
  capacity_liters: number | string;
  minimum_stock_liters: number | string;
  current_stock_liters: number | string;
  average_unit_cost: number | string;
  location: string | null;
  status: string;
}
interface ApiFuelControlBoard {
  summary: { tanks: number; purchases_pending: number; low_stock_tanks: number; total_stock_liters: number | string };
  tanks: ApiFuelTank[];
  queues: { low_stock_tanks: ApiFuelTank[] };
}

export interface FuelControlBoardLoadResult {
  board: FuelControlBoard;
  source: "api";
  message: string | null;
}

export async function loadFuelControlBoard(): Promise<FuelControlBoardLoadResult> {
  const payload = await apiFetch<ApiFuelControlBoard>("/api/v1/fuel-operations/board", { revalidate: 15 });
  return { board: mapFuelControlBoard(payload), source: "api", message: null };
}

function mapFuelControlBoard(payload: ApiFuelControlBoard): FuelControlBoard {
  return {
    summary: {
      tanks: payload.summary.tanks,
      purchasesPending: payload.summary.purchases_pending,
      lowStockTanks: payload.summary.low_stock_tanks,
      totalStockLiters: parseNumber(payload.summary.total_stock_liters),
    },
    tanks: payload.tanks.map(mapTank),
    queues: { lowStockTanks: payload.queues.low_stock_tanks.map(mapTank) },
  };
}

function mapTank(tank: ApiFuelTank): FuelTank {
  return {
    id: tank.id,
    code: tank.code,
    name: tank.name,
    fuelType: tank.fuel_type,
    capacityLiters: parseNumber(tank.capacity_liters),
    minimumStockLiters: parseNumber(tank.minimum_stock_liters),
    currentStockLiters: parseNumber(tank.current_stock_liters),
    averageUnitCost: parseNumber(tank.average_unit_cost),
    location: tank.location,
    status: tank.status,
  };
}

function parseNumber(value: number | string) {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : 0;
}
