import { apiFetch } from "./api";

export interface ControlTowerSummary {
  tripOrdersOpen: number;
  dispatchPending: number;
  dispatchBlocked: number;
  tripsInExecution: number;
  incidentsOpen: number;
  deliveryProofsPendingValidation: number;
  billingReady: number;
  activeWaivers: number;
  operationalExceptionsOpen: number;
  vehicleDocumentsExpiring: number;
  driverDocumentsExpiring: number;
  vehiclesActive: number;
  driversActive: number;
  tripsCreatedToday: number;
  costsReconciledTrips: number;
  transportCostTotal: number;
  contractRevenueTotal: number;
  marginTotal: number;
  negativeMarginTrips: number;
  closedTripsUnreconciled: number;
}
export interface BlockedDispatch {
  clearanceId: string;
  tripId: string;
  route: string;
  blockedReason: string;
  updatedAt: string;
}

export interface PendingDispatch {
  clearanceId: string;
  tripId: string;
  route: string;
  clearanceStatus: string;
  updatedAt: string;
}

export interface OpenIncident {
  incidentId: string;
  tripId: string;
  route: string;
  incidentType: string;
  severity: string;
  description: string;
  occurredAt: string;
}

export interface DelayedTrip {
  tripId: string;
  route: string;
  status: string;
  vehiclePlate: string | null;
  driverName: string | null;
  plannedArrival: string;
  delayMinutes: number;
}

export interface PendingDeliveryValidation {
  deliveryProofId: string;
  tripId: string;
  route: string;
  documentNumber: string | null;
  deliveredAt: string;
}

export interface DisputedDeliveryProof {
  deliveryProofId: string;
  tripId: string;
  route: string;
  documentNumber: string | null;
  deliveredAt: string;
  billingStatus: string;
}

export interface FailedChecklist {
  checklistId: string;
  vehicleId: string | null;
  vehiclePlate: string | null;
  driverId: string | null;
  driverName: string | null;
  type: string;
  completedAt: string | null;
}

export interface OperationalCloseCandidate {
  tripId: string;
  route: string;
  status: string;
  vehiclePlate: string | null;
  driverName: string | null;
  latestDeliveryProofId: string | null;
  latestDeliveryProofStatus: string | null;
  latestDeliveryProofNumber: string | null;
  hasBlockingIncident: boolean;
  readiness: string;
  updatedAt: string;
}

export interface NegativeMarginTrip {
  tripId: string;
  route: string;
  vehiclePlate: string | null;
  driverName: string | null;
  transportCost: number;
  revenue: number;
  margin: number;
  costsReconciledAt: string;
}

export interface DriverDespachoPending {
  tripId: string;
  route: string;
  status: string;
  vehiclePlate: string | null;
  driverName: string | null;
  distanceKm: number;
  minLongCourseKm: number;
  createdAt: string;
}

export interface OperationalException {
  exceptionId: string;
  entityType: string;
  entityId: string;
  exceptionType: string;
  severity: string;
  status: string;
  title: string;
  message: string;
  createdAt: string;
}

export interface ComplianceDocumentWarning {
  id: string;
  entityId: string;
  entityLabel: string;
  documentType: string;
  validUntil: string;
  daysUntilExpiry: number;
}

export interface ControlTower {
  date: string;
  summary: ControlTowerSummary;
  queues: {
    pendingDispatch: PendingDispatch[];
    blockedDispatch: BlockedDispatch[];
    openIncidents: OpenIncident[];
    delayedTrips: DelayedTrip[];
    pendingDeliveryValidation: PendingDeliveryValidation[];
    disputedDeliveryProofs: DisputedDeliveryProof[];
    failedChecklists: FailedChecklist[];
    operationalCloseCandidates: OperationalCloseCandidate[];
    negativeMarginTrips: NegativeMarginTrip[];
    driverDespachoPending: DriverDespachoPending[];
    operationalExceptions: OperationalException[];
    vehicleDocumentsExpiring: ComplianceDocumentWarning[];
    driverDocumentsExpiring: ComplianceDocumentWarning[];
  };
}

interface ApiControlTower {
  date: string;
  summary: {
    trip_orders_open: number;
    dispatch_pending: number;
    dispatch_blocked: number;
    trips_in_execution: number;
    incidents_open: number;
    delivery_proofs_pending_validation: number;
    billing_ready: number;
    active_waivers: number;
    operational_exceptions_open: number;
    vehicle_documents_expiring: number;
    driver_documents_expiring: number;
    vehicles_active: number;
    drivers_active: number;
    trips_created_today: number;
    costs_reconciled_trips: number;
    transport_cost_total: number;
    contract_revenue_total: number;
    margin_total: number;
    negative_margin_trips: number;
    closed_trips_unreconciled: number;
  };
  queues: {
    pending_dispatch?: Array<{
      clearance_id: string;
      trip_id: string;
      origin: string;
      destination: string;
      clearance_status: string;
      updated_at: string;
    }>;
    blocked_dispatch: Array<{
      clearance_id: string;
      trip_id: string;
      origin: string;
      destination: string;
      blocked_reason: string | null;
      updated_at: string;
    }>;
    open_incidents: Array<{
      incident_id: string;
      trip_id: string;
      origin: string;
      destination: string;
      incident_type: string;
      severity: string;
      description: string;
      occurred_at: string;
    }>;
    delayed_trips?: Array<{
      trip_id: string;
      origin: string;
      destination: string;
      status: string;
      vehicle_plate: string | null;
      driver_name: string | null;
      planned_arrival: string;
      delay_minutes: number;
    }>;
    pending_delivery_validation: Array<{
      delivery_proof_id: string;
      trip_id: string;
      origin: string;
      destination: string;
      document_number: string | null;
      delivered_at: string;
    }>;
    disputed_delivery_proofs?: Array<{
      delivery_proof_id: string;
      trip_id: string;
      origin: string;
      destination: string;
      document_number: string | null;
      delivered_at: string;
      billing_status: string;
    }>;
    failed_checklists?: Array<{
      checklist_id: string;
      vehicle_id: string | null;
      vehicle_plate: string | null;
      driver_id: string | null;
      driver_name: string | null;
      type: string;
      completed_at: string | null;
    }>;
    operational_close_candidates?: Array<{
      trip_id: string;
      origin: string;
      destination: string;
      status: string;
      vehicle_plate: string | null;
      driver_name: string | null;
      latest_delivery_proof_id: string | null;
      latest_delivery_proof_status: string | null;
      latest_delivery_proof_number: string | null;
      has_blocking_incident: boolean;
      readiness: string;
      updated_at: string;
    }>;
    negative_margin_trips?: Array<{
      trip_id: string;
      origin: string;
      destination: string;
      vehicle_plate: string | null;
      driver_name: string | null;
      transport_cost: number;
      revenue: number;
      margin: number;
      costs_reconciled_at: string;
    }>;
    driver_despacho_pending?: Array<{
      trip_id: string;
      origin: string;
      destination: string;
      status: string;
      vehicle_plate: string | null;
      driver_name: string | null;
      distance_km: number;
      min_long_course_km: number;
      created_at: string;
    }>;
    operational_exceptions: Array<{
      exception_id: string;
      entity_type: string;
      entity_id: string;
      exception_type: string;
      severity: string;
      status: string;
      title: string;
      message: string;
      created_at: string;
    }>;
    vehicle_documents_expiring: Array<{
      vehicle_id: string;
      vehicle_plate: string;
      document_type: string;
      valid_until: string;
      days_until_expiry: number;
    }>;
    driver_documents_expiring: Array<{
      driver_id: string;
      driver_name: string;
      document_type: string;
      valid_until: string;
      days_until_expiry: number;
    }>;
  };
}

export interface ControlTowerLoadResult {
  tower: ControlTower;
  source: "api";
  message: string | null;
}

export async function loadControlTower(): Promise<ControlTowerLoadResult> {
  const payload = await apiFetch<ApiControlTower>("/api/v1/control-tower", {
    revalidate: 15,
  });
  return { tower: mapControlTower(payload), source: "api", message: null };
}

export interface ImminentAlert {
  plan_id: string;
  plan_name: string;
  vehicle_id: string;
  vehicle_plate: string;
  next_due_at: string | null;
  next_due_km: number | null;
  current_km: number | null;
  trigger_type: "calendar" | "odometer" | "overdue";
}

export async function loadImminentMaintenanceAlerts(): Promise<ImminentAlert[]> {
  try {
    const data = await apiFetch<ImminentAlert[]>("/api/v1/workshop/imminent-alerts");
    return data;
  } catch {
    return [];
  }
}

function mapControlTower(payload: ApiControlTower): ControlTower {
  return {
    date: payload.date,
    summary: {
      tripOrdersOpen: payload.summary.trip_orders_open,
      dispatchPending: payload.summary.dispatch_pending,
      dispatchBlocked: payload.summary.dispatch_blocked,
      tripsInExecution: payload.summary.trips_in_execution,
      incidentsOpen: payload.summary.incidents_open,
      deliveryProofsPendingValidation: payload.summary.delivery_proofs_pending_validation,
      billingReady: payload.summary.billing_ready,
      activeWaivers: payload.summary.active_waivers,
      operationalExceptionsOpen: payload.summary.operational_exceptions_open,
      vehicleDocumentsExpiring: payload.summary.vehicle_documents_expiring,
      driverDocumentsExpiring: payload.summary.driver_documents_expiring,
      vehiclesActive: payload.summary.vehicles_active,
      driversActive: payload.summary.drivers_active,
      tripsCreatedToday: payload.summary.trips_created_today,
      costsReconciledTrips: payload.summary.costs_reconciled_trips ?? 0,
      transportCostTotal: Number(payload.summary.transport_cost_total ?? 0),
      contractRevenueTotal: Number(payload.summary.contract_revenue_total ?? 0),
      marginTotal: Number(payload.summary.margin_total ?? 0),
      negativeMarginTrips: payload.summary.negative_margin_trips ?? 0,
      closedTripsUnreconciled: payload.summary.closed_trips_unreconciled ?? 0,
    },
    queues: {
      pendingDispatch: (payload.queues.pending_dispatch ?? []).map((item) => ({
        clearanceId: item.clearance_id,
        tripId: item.trip_id,
        route: `${item.origin} -> ${item.destination}`,
        clearanceStatus: item.clearance_status,
        updatedAt: item.updated_at,
      })),
      blockedDispatch: payload.queues.blocked_dispatch.map((item) => ({
        clearanceId: item.clearance_id,
        tripId: item.trip_id,
        route: `${item.origin} -> ${item.destination}`,
        blockedReason: item.blocked_reason ?? "Motivo não indicado",
        updatedAt: item.updated_at,
      })),
      openIncidents: payload.queues.open_incidents.map((item) => ({
        incidentId: item.incident_id,
        tripId: item.trip_id,
        route: `${item.origin} -> ${item.destination}`,
        incidentType: item.incident_type,
        severity: item.severity,
        description: item.description,
        occurredAt: item.occurred_at,
      })),
      delayedTrips: (payload.queues.delayed_trips ?? []).map((item) => ({
        tripId: item.trip_id,
        route: `${item.origin} -> ${item.destination}`,
        status: item.status,
        vehiclePlate: item.vehicle_plate,
        driverName: item.driver_name,
        plannedArrival: item.planned_arrival,
        delayMinutes: item.delay_minutes,
      })),
      pendingDeliveryValidation: payload.queues.pending_delivery_validation.map((item) => ({
        deliveryProofId: item.delivery_proof_id,
        tripId: item.trip_id,
        route: `${item.origin} -> ${item.destination}`,
        documentNumber: item.document_number,
        deliveredAt: item.delivered_at,
      })),
      disputedDeliveryProofs: (payload.queues.disputed_delivery_proofs ?? []).map((item) => ({
        deliveryProofId: item.delivery_proof_id,
        tripId: item.trip_id,
        route: `${item.origin} -> ${item.destination}`,
        documentNumber: item.document_number,
        deliveredAt: item.delivered_at,
        billingStatus: item.billing_status,
      })),
      failedChecklists: (payload.queues.failed_checklists ?? []).map((item) => ({
        checklistId: item.checklist_id,
        vehicleId: item.vehicle_id,
        vehiclePlate: item.vehicle_plate,
        driverId: item.driver_id,
        driverName: item.driver_name,
        type: item.type,
        completedAt: item.completed_at,
      })),
      operationalCloseCandidates: (payload.queues.operational_close_candidates ?? []).map(
        (item) => ({
          tripId: item.trip_id,
          route: `${item.origin} -> ${item.destination}`,
          status: item.status,
          vehiclePlate: item.vehicle_plate,
          driverName: item.driver_name,
          latestDeliveryProofId: item.latest_delivery_proof_id,
          latestDeliveryProofStatus: item.latest_delivery_proof_status,
          latestDeliveryProofNumber: item.latest_delivery_proof_number,
          hasBlockingIncident: item.has_blocking_incident,
          readiness: item.readiness,
          updatedAt: item.updated_at,
        }),
      ),
      negativeMarginTrips: (payload.queues.negative_margin_trips ?? []).map((item) => ({
        tripId: item.trip_id,
        route: `${item.origin} -> ${item.destination}`,
        vehiclePlate: item.vehicle_plate,
        driverName: item.driver_name,
        transportCost: Number(item.transport_cost ?? 0),
        revenue: Number(item.revenue ?? 0),
        margin: Number(item.margin ?? 0),
        costsReconciledAt: item.costs_reconciled_at,
      })),
      driverDespachoPending: (payload.queues.driver_despacho_pending ?? []).map((item) => ({
        tripId: item.trip_id,
        route: `${item.origin} -> ${item.destination}`,
        status: item.status,
        vehiclePlate: item.vehicle_plate,
        driverName: item.driver_name,
        distanceKm: Number(item.distance_km ?? 0),
        minLongCourseKm: Number(item.min_long_course_km ?? 0),
        createdAt: item.created_at,
      })),
      operationalExceptions: payload.queues.operational_exceptions.map((item) => ({
        exceptionId: item.exception_id,
        entityType: item.entity_type,
        entityId: item.entity_id,
        exceptionType: item.exception_type,
        severity: item.severity,
        status: item.status,
        title: item.title,
        message: item.message,
        createdAt: item.created_at,
      })),
      vehicleDocumentsExpiring: payload.queues.vehicle_documents_expiring.map((item) => ({
        id: `vehicle-doc-${item.vehicle_id}-${item.document_type}`,
        entityId: item.vehicle_id,
        entityLabel: item.vehicle_plate,
        documentType: item.document_type,
        validUntil: item.valid_until,
        daysUntilExpiry: item.days_until_expiry,
      })),
      driverDocumentsExpiring: payload.queues.driver_documents_expiring.map((item) => ({
        id: `driver-doc-${item.driver_id}-${item.document_type}`,
        entityId: item.driver_id,
        entityLabel: item.driver_name,
        documentType: item.document_type,
        validUntil: item.valid_until,
        daysUntilExpiry: item.days_until_expiry,
      })),
    },
  };
}
