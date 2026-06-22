"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

interface ApiConfig {
  apiBaseUrl: string;
  tenantId: string | null;
  token: string;
}

type TransportCargoAction =
  | {
      kind: "evaluate-delivery-sla";
    }
  | {
      kind: "approve-dispatch-clearance";
      tripId: string;
    }
  | {
      kind: "dispatch-trip";
      tripId: string;
    }
  | {
      kind: "validate-delivery-proof";
      tripId: string;
      deliveryProofId: string;
    }
  | {
      kind: "resolve-incident";
      tripId: string;
      incidentId: string;
    }
  | {
      kind: "resolve-delivery-dispute";
      tripId: string;
      deliveryProofId: string;
      outcome: "validated" | "rejected";
    }
  | {
      kind: "resolve-checklist-failure";
      checklistId: string;
    }
  | {
      kind: "operational-close";
      tripId: string;
    };

interface TransportCargoActionsProps {
  action: TransportCargoAction;
  apiConfig: ApiConfig;
  label: string;
}

export function TransportCargoActions({ action, apiConfig, label }: TransportCargoActionsProps) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!apiConfig.tenantId) {
    return <small className="text-muted text-sm">Acção indisponível sem API</small>;
  }

  async function runAction() {
    setBusy(true);
    setError(null);

    try {
      const { path, body, key } = actionRequest(action);
      const response = await fetch(`${apiConfig.apiBaseUrl}${path}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiConfig.token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": key,
          "X-Tenant-Id": apiConfig.tenantId ?? "",
        },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const message =
          payload?.error?.message ?? payload?.detail ?? `API respondeu HTTP ${response.status}`;
        throw new Error(message);
      }
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Operação falhou.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <Button
        disabled={busy}
        onClick={runAction}
        type="button"
        variant="ghost"
        size="sm"
      >
        {busy ? "A processar..." : label}
      </Button>
      {error ? <small className="text-error text-xs">{error}</small> : null}
    </div>
  );
}

function actionRequest(action: TransportCargoAction) {
  if (action.kind === "evaluate-delivery-sla") {
    return {
      path: "/api/v1/trips/sla/evaluate",
      key: `manager:transport:evaluate-delivery-sla:${new Date().toISOString().slice(0, 13)}`,
      body: {},
    };
  }

  if (action.kind === "approve-dispatch-clearance") {
    return {
      path: `/api/v1/trips/${action.tripId}/dispatch-clearance/approve`,
      key: `manager:transport:approve-dispatch-clearance:${action.tripId}`,
      body: {
        vehicle_checked: true,
        driver_checked: true,
        documents_checked: true,
        load_permit_checked: true,
        cargo_checked: true,
        fuel_advance_checked: true,
        route_risk_checked: true,
      },
    };
  }

  if (action.kind === "dispatch-trip") {
    return {
      path: `/api/v1/trips/${action.tripId}/dispatch`,
      key: `manager:transport:dispatch-trip:${action.tripId}`,
      body: {
        dispatched_at: new Date().toISOString(),
        notes: "Despachado no board Transporte e Carga.",
      },
    };
  }

  if (action.kind === "validate-delivery-proof") {
    return {
      path: `/api/v1/trips/${action.tripId}/delivery-proof/${action.deliveryProofId}/validate`,
      key: `manager:transport:validate-delivery-proof:${action.deliveryProofId}`,
      body: {
        validation_method: "manager_transport_board",
        notes: "Validado no board Transporte e Carga.",
      },
    };
  }

  if (action.kind === "resolve-incident") {
    return {
      path: `/api/v1/trips/${action.tripId}/incidents/${action.incidentId}/resolve`,
      key: `manager:transport:resolve-incident:${action.incidentId}`,
      body: {
        resolution_notes: "Incidente resolvido no board Transporte e Carga.",
        resolved_at: new Date().toISOString(),
      },
    };
  }

  if (action.kind === "resolve-delivery-dispute") {
    const label = action.outcome === "validated" ? "aceite" : "rejeitada";
    return {
      path: `/api/v1/trips/${action.tripId}/delivery-proof/${action.deliveryProofId}/resolve-dispute`,
      key: `manager:transport:resolve-delivery-dispute:${action.deliveryProofId}:${action.outcome}`,
      body: {
        outcome: action.outcome,
        validation_method: "manager_transport_board",
        resolution_notes: `Disputa documental ${label} no board Transporte e Carga.`,
      },
    };
  }

  if (action.kind === "resolve-checklist-failure") {
    return {
      path: `/api/v1/checklists/${action.checklistId}/resolve-failure`,
      key: `manager:transport:resolve-checklist-failure:${action.checklistId}`,
      body: {
        resolution_notes: "Checklist falhado tratado no board Transporte e Carga.",
        resolved_at: new Date().toISOString(),
      },
    };
  }

  return {
    path: `/api/v1/trips/${action.tripId}/close`,
    key: `manager:transport:operational-close:${action.tripId}`,
    body: {
      closed_at: new Date().toISOString(),
      notes: "Fecho operacional executado no board Transporte e Carga.",
    },
  };
}
