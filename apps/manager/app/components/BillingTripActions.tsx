"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import type { BillingTrip, ContractOption } from "../lib/billing-api";

interface ApiConfig {
  apiBaseUrl: string;
  tenantId: string | null;
  token: string;
}

interface BillingTripActionsProps {
  trip: BillingTrip;
  contracts: ContractOption[];
  apiConfig: ApiConfig;
}

export function BillingTripActions({ trip, contracts, apiConfig }: BillingTripActionsProps) {
  const router = useRouter();
  const [contractId, setContractId] = useState(contracts[0]?.id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canUseApi = Boolean(apiConfig.tenantId);
  const selectedContract = useMemo(
    () => contracts.find((contract) => contract.id === contractId) ?? null,
    [contractId, contracts],
  );

  async function callApi(path: string, body: unknown) {
    if (!apiConfig.tenantId) {
      setError("Configure ROTAS_TENANT_ID.");
      return null;
    }

    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${apiConfig.apiBaseUrl}${path}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiConfig.token}`,
          "Content-Type": "application/json",
          "X-Tenant-Id": apiConfig.tenantId,
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
      return payload;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Operacao falhou.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function associateContract() {
    if (!contractId) {
      setError("Seleccione um contrato.");
      return;
    }
    await callApi(`/api/v1/trips/${trip.id}/associate-contract`, {
      contract_id: contractId,
    });
  }

  async function validateDeliveryProof() {
    if (!trip.deliveryProofId) {
      setError("Esta viagem ainda nao tem prova de descarga.");
      return;
    }
    await callApi(`/api/v1/trips/${trip.id}/delivery-proof/${trip.deliveryProofId}/validate`, {
      validation_method: "manual_review",
      notes: "Validado no dashboard do gestor.",
    });
  }

  async function createAndIssueBillingDocument() {
    if (!trip.contractId || !trip.client || !trip.contractReference) {
      setError("A viagem precisa de contrato antes da cobranca.");
      return;
    }

    const period = billingPeriodFor(trip.deliveredAt);
    const document = await callApi("/api/v1/billing/documents", {
      contract_id: trip.contractId,
      client_name: trip.client,
      contract_reference: trip.contractReference,
      billing_period_start: period.start,
      billing_period_end: period.end,
      currency: "MZN",
      trip_ids: [trip.id],
    });

    if (document?.id) {
      await callApi(`/api/v1/billing/documents/${document.id}/issue`, {
        issued_at: new Date().toISOString(),
      });
    }
  }

  if (!canUseApi) {
    return <span className="muted-line">Acções indisponíveis sem API</span>;
  }

  if (trip.status === "uncontracted") {
    return (
      <div className="row-actions">
        <select
          aria-label="Contrato"
          value={contractId}
          onChange={(event) => setContractId(event.target.value)}
        >
          {contracts.length === 0 ? <option value="">Sem contratos</option> : null}
          {contracts.map((contract) => (
            <option key={contract.id} value={contract.id}>
              {contract.contractReference} · {contract.clientName}
            </option>
          ))}
        </select>
        <button disabled={busy || !selectedContract} onClick={associateContract} type="button">
          Associar
        </button>
        {error ? <small>{error}</small> : null}
      </div>
    );
  }

  if (trip.status === "pending_delivery_validation") {
    return (
      <div className="row-actions">
        <button disabled={busy || !trip.deliveryProofId} onClick={validateDeliveryProof} type="button">
          Validar descarga
        </button>
        {error ? <small>{error}</small> : null}
      </div>
    );
  }

  if (trip.status === "billable") {
    return (
      <div className="row-actions">
        <button disabled={busy} onClick={createAndIssueBillingDocument} type="button">
          Cobrar
        </button>
        {error ? <small>{error}</small> : null}
      </div>
    );
  }

  return <span className="muted-line">Sem acção</span>;
}

function billingPeriodFor(deliveredAt: string) {
  const date = deliveredAt && deliveredAt !== "-" ? new Date(`${deliveredAt}T00:00:00Z`) : new Date();
  const start = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
  const end = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 1));
  return {
    start: start.toISOString(),
    end: end.toISOString(),
  };
}
