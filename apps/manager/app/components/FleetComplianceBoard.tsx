"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarCheck, FileWarning, Truck, Users } from "lucide-react";

import { PageHeader } from "@/app/components/ui/PageHeader";
import { StatusBadge } from "@/app/components/ui/StatusBadge";

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
    <section className="mt-6" aria-labelledby="compliance-title">
      <PageHeader
        eyebrow="Frota e Pessoas"
        title="Compliance documental"
        description="Renovação operacional de documentos antes de bloquearem a atribuição."
        actions={
          <span className="flex items-center gap-1.5 text-[12px] text-muted">
            <CalendarCheck size={14} />
            {vehicleItems.length + driverItems.length} avisos
          </span>
        }
      />

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
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <header className="flex items-start gap-3 px-4 py-3 border-b border-border bg-surface-2">
        <span className="flex items-center justify-center h-6 w-6 rounded flex-shrink-0 bg-warning-bg text-warning">
          <Icon size={13} />
        </span>
        <div>
          <h3 className="text-[14px] font-semibold text-ink m-0">{title}</h3>
          <p className="text-muted text-[12px] m-0">{items.length} documentos em atenção</p>
        </div>
      </header>
      <div className="divide-y divide-border">
        {items.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-[12px] text-muted">{emptyLabel}</p>
          </div>
        ) : null}
        {items.map((item) => (
          <ComplianceItem
            apiConfig={apiConfig}
            entityType={entityType}
            item={item}
            key={item.id}
          />
        ))}
      </div>
    </div>
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
    <div className="px-4 py-3 text-sm">
      {/* Document info row */}
      <div className="flex gap-2 mb-2">
        <FileWarning size={15} className="flex-none text-warning mt-0.5" />
        <div className="min-w-0">
          <strong className="block text-[13px] text-ink">{item.entityLabel}</strong>
          <span className="block text-muted text-[12px] mt-0.5">
            {documentTypeLabel(item.documentType)}
          </span>
          <div className="flex items-center gap-2 mt-1">
            <StatusBadge
              status={item.daysUntilExpiry <= 7 ? "expired" : "expiring_soon"}
              label={`${item.daysUntilExpiry} dias`}
            />
            <small className="text-muted text-[11px]">{formatDateOnly(item.validUntil)}</small>
          </div>
        </div>
      </div>
      {/* Renew form — full width below info */}
      <div className="flex gap-2 flex-wrap">
        <input
          aria-label="Nova validade"
          type="date"
          value={validUntil}
          onChange={(event) => setValidUntil(event.target.value)}
          className="min-h-[32px] border border-border rounded-md bg-white text-ink px-2 text-[12px] flex-1 min-w-[130px]"
        />
        <input
          aria-label="Referência"
          placeholder="Referência doc."
          value={reference}
          onChange={(event) => setReference(event.target.value)}
          className="min-h-[32px] border border-border rounded-md bg-white text-ink px-2 text-[12px] flex-1 min-w-[110px]"
        />
        <button
          disabled={busy}
          onClick={renew}
          type="button"
          className="min-h-[32px] px-3 text-[12px] font-bold border border-border rounded-md bg-white text-ink hover:bg-surface-2 disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap"
        >
          {busy ? "A guardar..." : "Renovar"}
        </button>
      </div>
      {error ? <small className="block mt-1 text-error text-[12px]">{error}</small> : null}
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
    passport: "Passaporte",
    bi: "Bilhete de Identidade",
    inspection: "Inspecção",
    insurance: "Seguro",
    iav: "IAV",
    sign_tax: "Taxa de Letreiro",
    cargo_book: "Caderneta de Carga",
    international_license: "Licença Internacional",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function formatDateOnly(value: string) {
  return new Intl.DateTimeFormat("pt-MZ", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}
