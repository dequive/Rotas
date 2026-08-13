import { apiFetch } from "./api";

export interface FleetHistoryEvent {
  occurredAt: string | null;
  source: string;
  eventType: string;
  summary: string;
  referenceType: string;
  referenceId: string;
  details: Record<string, unknown>;
}

export interface VehicleHistory {
  vehicle: { id: string; plate: string; status: string; currentKm: number };
  items: FleetHistoryEvent[];
}

export interface DriverHistory {
  driver: { id: string; fullName: string; status: string; score: number };
  items: FleetHistoryEvent[];
}

export interface FleetHistoryLoadResult {
  vehicleHistory: VehicleHistory | null;
  driverHistory: DriverHistory | null;
  source: "api";
  message: string | null;
}

interface ApiVehicle { id: string }
interface ApiDriver { id: string }
interface ApiHistoryEvent {
  occurred_at: string | null;
  source: string;
  event_type: string;
  summary: string;
  reference_type: string;
  reference_id: string;
  details: Record<string, unknown>;
}
interface ApiVehicleHistory {
  vehicle: { id: string; plate: string; status: string; current_km: number };
  items: ApiHistoryEvent[];
}
interface ApiDriverHistory {
  driver: { id: string; full_name: string; status: string; score: number };
  items: ApiHistoryEvent[];
}

export async function loadFleetHistories(): Promise<FleetHistoryLoadResult> {
  const [vehicles, drivers] = await Promise.all([
    apiFetch<ApiVehicle[]>("/api/v1/vehicles?limit=1", { revalidate: 30 }),
    apiFetch<ApiDriver[]>("/api/v1/drivers?limit=1", { revalidate: 30 }),
  ]);
  if (vehicles.length === 0 || drivers.length === 0) {
    return {
      vehicleHistory: null,
      driverHistory: null,
      source: "api",
      message: "Registe ao menos uma viatura e um motorista para ver históricos.",
    };
  }
  const [vehicleHistory, driverHistory] = await Promise.all([
    apiFetch<ApiVehicleHistory>(`/api/v1/vehicles/${vehicles[0].id}/history?limit=8`, { revalidate: 15 }),
    apiFetch<ApiDriverHistory>(`/api/v1/drivers/${drivers[0].id}/history?limit=8`, { revalidate: 15 }),
  ]);
  return {
    vehicleHistory: mapVehicleHistory(vehicleHistory),
    driverHistory: mapDriverHistory(driverHistory),
    source: "api",
    message: null,
  };
}

function mapVehicleHistory(payload: ApiVehicleHistory): VehicleHistory {
  return {
    vehicle: {
      id: payload.vehicle.id,
      plate: payload.vehicle.plate,
      status: payload.vehicle.status,
      currentKm: payload.vehicle.current_km,
    },
    items: payload.items.map(mapEvent),
  };
}

function mapDriverHistory(payload: ApiDriverHistory): DriverHistory {
  return {
    driver: {
      id: payload.driver.id,
      fullName: payload.driver.full_name,
      status: payload.driver.status,
      score: payload.driver.score,
    },
    items: payload.items.map(mapEvent),
  };
}

function mapEvent(item: ApiHistoryEvent): FleetHistoryEvent {
  return {
    occurredAt: item.occurred_at,
    source: item.source,
    eventType: item.event_type,
    summary: item.summary,
    referenceType: item.reference_type,
    referenceId: item.reference_id,
    details: item.details,
  };
}
