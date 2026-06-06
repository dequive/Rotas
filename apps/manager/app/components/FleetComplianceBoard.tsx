"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarCheck, FileWarning, Truck, Users } from "lucide-react";

import type { ComplianceDocumentWarning, ControlTowerLoadResult } from "../lib/control-tower-api";

interface ApiConfig {
  apiBaseUrl: string;
  tenantId: string | null;
  token: string;
}

interface FleetComplianceBoardProps {
  apiConfig: ApiConfig;
  result: ControlTowerLoadResult;
}

export function FleetComplianceBoard({ apiConfig, result }: FleetComplianceBoardProps) {
  const vehicleItems = result.tower.queues.vehicleDocumentsExpiring;
  const driverItems = result.tower.queues.driverDocumentsExpiring;

  return (
    <section className="domain-section" aria-labelledby="compliance-title">
      <div className="domain-heading">
        <div className="title">
          <span className="eyebrow">Frota e Pessoas</span>
          <h2 id="compliance-title">Compliance documental</h2>
          <p>Renovação operacional de documentos antes de bloquearem a atribuição.</p>
        </div>
        <span className="module-state">
          <CalendarCheck size={15} />
          {vehicleItems.length + driverItems.length} avisos
        </span>
      </div>

      <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
        <ComplianceColumn
          apiConfig={apiConfig}
          emptyLabel="Sem documentos de viatura perto do vencimento."
          entityType="vehicle"
          icon={Truck}
          items={vehicleItems}
          title="Viaturas"
        />
        <ComplianceColumn
          apiConfig={apiConfig}
          emptyLabel="Sem documentos de motorista perto do vencimento."
          entityType="driver"
          icon={Users}
          items={driverItems}
          title="Motoristas"
        />
      </div>
    </section>
  );
}

function ComplianceColumn({
  apiConfig,
  emptyLabel,
  entityType,
  icon: Icon,
  items,
  title,
}: {
  apiConfig: ApiConfig;
  emptyLabel: string;
  entityType: "vehicle" | "driver";
  icon: typeof Truck;
  items: ComplianceDocumentWarning[];
  title: string;
}) {
  return (
    <article className="bg-panel border border-line rounded-lg p-4">
      <header>
        <span className="queue-icon orange">
          <Icon size={16} />
        </span>
        <div>
          <h3>{title}</h3>
          <p>{items.length} documentos em atenção</p>
        </div>
      </header>
      <div className="grid gap-2">
        {items.length === 0 ? <p className="empty-state">{emptyLabel}</p> : null}
        {items.map((item) => (
          <ComplianceItem
            apiConfig={apiConfig}
            entityType={entityType}
            item={item}
            key={item.id}
          />
        ))}
      </div>
    </article>
  );
}

function ComplianceItem({
  apiConfig,
  entityType,
  item,
}: {
  apiConfig: ApiConfig;
  entityType: "vehicle" | "driver";
  item: ComplianceDocumentWarning;
}) {
  const router = useRouter();
  const defaultValidUntil = defaultRenewalDate(item.validUntil);
  const [validUntil, setValidUntil] = useState(defaultValidUntil);
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function renew() {
    if (!apiConfig.tenantId) {
      setError("Acção indisponível sem API.");
      return;
    }
    if (!validUntil) {
      setError("Informe a nova validade.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const path =
        entityType === "vehicle"
          ? `/api/v1/vehicles/${item.entityId}/documents/${item.documentType}/renew`
          : `/api/v1/drivers/${item.entityId}/documents/${item.documentType}/renew`;
      const response = await fetch(`${apiConfig.apiBaseUrl}${path}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiConfig.token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": `manager:fleet:${entityType}:renew:${item.entityId}:${item.documentType}:${validUntil}`,
          "X-Tenant-Id": apiConfig.tenantId,
        },
        body: JSON.stringify({
          valid_until: validUntil,
          reference: reference || null,
          notes: "Renovado no board Frota e Pessoas.",
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const message =
          payload?.error?.message ?? payload?.detail ?? `API respondeu HTTP ${response.status}`;
        throw new Error(message);
      }
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Renovação falhou.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center justify-between py-2 border-b border-line last:border-0 text-sm">
      <div className="min-w-0 flex gap-2">
        <FileWarning size={15} className="flex-none text-orange mt-0.5" />
        <div>
          <strong className="block text-[13px]">{item.entityLabel}</strong>
          <span className="block text-muted text-[12px] mt-0.5">
            {documentTypeLabel(item.documentType)} vence em {item.daysUntilExpiry} dias
          </span>
          <small className="block text-muted text-[12px]">{formatDateOnly(item.validUntil)}</small>
        </div>
      </div>
      <div className="fleet-renew-form">
        <input
          aria-label="Nova validade"
          type="date"
          value={validUntil}
          onChange={(event) => setValidUntil(event.target.value)}
        />
        <input
          aria-label="Referência"
          placeholder="Referência"
          value={reference}
          onChange={(event) => setReference(event.target.value)}
        />
        <button disabled={busy} onClick={renew} type="button">
          {busy ? "A guardar..." : "Renovar"}
        </button>
        {error ? <small>{error}</small> : null}
      </div>
    </div>
  );
}

function defaultRenewalDate(validUntil: string) {
  const base = new Date(`${validUntil}T00:00:00Z`);
  if (Number.isNaN(base.getTime())) {
    return "";
  }
  return new Date(Date.UTC(base.getUTCFullYear() + 1, base.getUTCMonth(), base.getUTCDate()))
    .toISOString()
    .slice(0, 10);
}

function documentTypeLabel(value: string) {
  const labels: Record<string, string> = {
    driving_license: "Carta de condução",
    inatter_license: "Licença INATTER",
    inspection: "Inspecção",
    insurance: "Seguro",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function formatDateOnly(value: string) {
  return new Intl.DateTimeFormat("pt-MZ", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}
