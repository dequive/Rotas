"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { bffRequest } from "@/app/lib/bff";
import { ModalDialog } from "./ui/ModalDialog";

interface ApiConfig {
  tenantId: string | null;
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

type DispatchChecks = {
  vehicle_checked: boolean;
  driver_checked: boolean;
  documents_checked: boolean;
  load_permit_checked: boolean;
  cargo_checked: boolean;
  fuel_advance_checked: boolean;
  route_risk_checked: boolean;
};

const emptyDispatchChecks: DispatchChecks = {
  vehicle_checked: false,
  driver_checked: false,
  documents_checked: false,
  load_permit_checked: false,
  cargo_checked: false,
  fuel_advance_checked: false,
  route_risk_checked: false,
};

const dispatchCheckLabels: Array<[keyof DispatchChecks, string]> = [
  ["vehicle_checked", "Viatura verificada"],
  ["driver_checked", "Motorista verificado"],
  ["documents_checked", "Documentos verificados"],
  ["load_permit_checked", "Load permit verificado"],
  ["cargo_checked", "Carga verificada"],
  ["fuel_advance_checked", "Adiantamento de combustível verificado"],
  ["route_risk_checked", "Risco da rota verificado"],
];

export function TransportCargoActions({ action, apiConfig, label }: TransportCargoActionsProps) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [dispatchChecks, setDispatchChecks] = useState(emptyDispatchChecks);

  if (!apiConfig.tenantId) {
    return <small className="text-muted text-sm">Acção indisponível sem API</small>;
  }

  async function runAction() {
    if (action.kind === "approve-dispatch-clearance") {
      setDispatchChecks(emptyDispatchChecks);
      setError(null);
      setApprovalOpen(true);
      return;
    }
    await submitAction();
  }

  async function submitAction(checks?: DispatchChecks) {
    setBusy(true);
    setError(null);

    try {
      const { path, body, key } = actionRequest(action, checks);
      const response = await bffRequest(path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": key,
        },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const message =
          payload?.error?.message ?? payload?.detail ?? `API respondeu HTTP ${response.status}`;
        throw new Error(message);
      }
      setApprovalOpen(false);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Operação falhou.");
    } finally {
      setBusy(false);
    }
  }

  async function submitApproval(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitAction(dispatchChecks);
  }

  const allDispatchChecksConfirmed = Object.values(dispatchChecks).every(Boolean);

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
      <ModalDialog
        open={approvalOpen}
        onClose={() => setApprovalOpen(false)}
        title="Verificação da autorização de saída"
      >
        <form onSubmit={submitApproval} className="flex flex-col gap-4 px-6 pb-6 pt-4">
          <p className="text-sm text-muted">
            Confirme cada controlo com base na evidência operacional. A aprovação fica auditada.
          </p>
          <div className="grid gap-3">
            {dispatchCheckLabels.map(([key, checkLabel]) => (
              <label key={key} className="flex items-center gap-2 text-sm font-semibold text-ink">
                <input
                  type="checkbox"
                  checked={dispatchChecks[key]}
                  onChange={(event) =>
                    setDispatchChecks((current) => ({
                      ...current,
                      [key]: event.target.checked,
                    }))
                  }
                />
                {checkLabel}
              </label>
            ))}
          </div>
          {error ? <p role="alert" className="text-sm text-error">{error}</p> : null}
          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <Button type="button" variant="secondary" onClick={() => setApprovalOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!allDispatchChecksConfirmed || busy}>
              {busy ? "A aprovar..." : "Confirmar aprovação"}
            </Button>
          </div>
        </form>
      </ModalDialog>
    </div>
  );
}

function actionRequest(action: TransportCargoAction, dispatchChecks?: DispatchChecks) {
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
      key: `manager:transport:approve-dispatch-clearance:${action.tripId}:${crypto.randomUUID()}`,
      body: dispatchChecks ?? emptyDispatchChecks,
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
