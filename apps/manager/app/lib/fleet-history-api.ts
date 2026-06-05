import { apiFetch } from "./api";
import { getApiConfig } from "./billing-api";

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
  vehicle: {
    id: string;
    plate: string;
    status: string;
    currentKm: number;
  };
  items: FleetHistoryEvent[];
}

export interface DriverHistory {
  driver: {
    id: string;
    fullName: string;
    status: string;
    score: number;
  };
  items: FleetHistoryEvent[];
}

export interface FleetHistoryLoadResult {
  vehicleHistory: VehicleHistory;
  driverHistory: DriverHistory;
  source: "api" | "fallback";
  message: string | null;
}

interface ApiVehicle {
  id: string;
}

interface ApiDriver {
  id: string;
}

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
  vehicle: {
    id: string;
    plate: string;
    status: string;
    current_km: number;
  };
  items: ApiHistoryEvent[];
}

interface ApiDriverHistory {
  driver: {
    id: string;
    full_name: string;
    status: string;
    score: number;
  };
  items: ApiHistoryEvent[];
}

const fallbackVehicleHistory: VehicleHistory = {
  vehicle: {
    id: "vehicle-demo-001",
    plate: "MPT-00-RT",
    status: "active",
    currentKm: 126400,
  },
  items: [
    {
      occurredAt: "2026-06-10T08:35:00Z",
      source: "trips",
      eventType: "trip.in_progress",
      summary: "Trip Maputo -> Beira is in_progress.",
      referenceType: "trip",
      referenceId: "TRP-018",
      details: {
        driver_id: "DRV-001",
        km_start: 126400,
        billing_status: "not_billable",
      },
    },
    {
      occurredAt: "2026-06-10T07:50:00Z",
      source: "checklists",
      eventType: "checklist.passed",
      summary: "pre_departure checklist passed.",
      referenceType: "checklist",
      referenceId: "CHK-021",
      details: {
        driver_id: "DRV-001",
        duration_seconds: 420,
      },
    },
    {
      occurredAt: "2026-06-09T16:20:00Z",
      source: "fuel_operations",
      eventType: "fuel.internal_refuel",
      summary: "Internal refuel of 180 L.",
      referenceType: "vehicle_refuel",
      referenceId: "REF-029",
      details: {
        driver_id: "DRV-001",
        odometer_reading: 126380,
        total_cost: 13500,
      },
    },
  ],
};

const fallbackDriverHistory: DriverHistory = {
  driver: {
    id: "driver-demo-001",
    fullName: "Ana Mucavele",
    status: "active",
    score: 96,
  },
  items: [
    {
      occurredAt: "2026-06-10T08:35:00Z",
      source: "trips",
      eventType: "trip.in_progress",
      summary: "Trip Maputo -> Beira is in_progress.",
      referenceType: "trip",
      referenceId: "TRP-018",
      details: {
        vehicle_id: "VEH-001",
        km_start: 126400,
        billing_status: "not_billable",
      },
    },
    {
      occurredAt: "2026-06-10T07:50:00Z",
      source: "checklists",
      eventType: "checklist.passed",
      summary: "pre_departure checklist passed.",
      referenceType: "checklist",
      referenceId: "CHK-021",
      details: {
        vehicle_id: "VEH-001",
        duration_seconds: 420,
      },
    },
    {
      occurredAt: "2026-06-08T12:10:00Z",
      source: "operations",
      eventType: "waiver.active",
      summary: "medium expired_warning waiver.",
      referenceType: "operational_waiver",
      referenceId: "WVR-006",
      details: {
        expires_at: "2026-06-15T23:59:00Z",
      },
    },
  ],
};

export async function loadFleetHistories(): Promise<FleetHistoryLoadResult> {
  try {
    const [vehicles, drivers] = await Promise.all([
      apiFetch<ApiVehicle[]>("/api/v1/vehicles?limit=1", { revalidate: 30 }),
      apiFetch<ApiDriver[]>("/api/v1/drivers?limit=1", { revalidate: 30 }),
    ]);

    if (vehicles.length === 0 || drivers.length === 0) {
      return fallbackResult("Registe ao menos uma viatura e um motorista para ver históricos reais.");
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
  } catch (error) {
    return fallbackResult(error instanceof Error ? `Históricos: ${error.message}` : "Indisponível.");
  }
}

function fallbackResult(message: string): FleetHistoryLoadResult {
  return {
    vehicleHistory: fallbackVehicleHistory,
    driverHistory: fallbackDriverHistory,
    source: "fallback",
    message,
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
