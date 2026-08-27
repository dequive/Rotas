import {
  AlertTriangle,
  Clock3,
  FileCheck2,
  FileText,
} from "lucide-react";
import Link from "next/link";

import { SidebarLayout } from "../../components/SidebarLayout";
import { KpiCard } from "../../components/ui/KpiCard";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { requireSession } from "../../lib/auth";
import { loadVehicles } from "../../lib/vehicles-api";
import { loadWorkOrders } from "../../lib/workshop-api";

const money = new Intl.NumberFormat("pt-MZ", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export default async function WorkshopBillingPage() {
  await requireSession();
  const [result, vehicles] = await Promise.all([
    loadWorkOrders("closed"),
    loadVehicles(),
  ]);
  const vehicleById = new Map(vehicles.map((vehicle) => [vehicle.id, vehicle]));
  const pending = result.data.filter(
    (order) => order.billing_status === "billing_pending",
  );
  const drafts = result.data.filter(
    (order) => order.billing_status === "draft_created",
  );
  const failures = result.data.filter(
    (order) => order.billing_status === "billing_failed",
  );
  const reconciledCost = result.data.reduce(
    (total, order) => total + (order.actual_cost ?? 0),
    0,
  );

  return (
    <SidebarLayout active="faturacao-oficina">
      <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6">
        <PageHeader
          eyebrow="Oficina Auto"
          title="Pipeline de faturação"
          description="Ordens concluídas, criação assíncrona do rascunho fiscal e emissão controlada no detalhe da OS."
        />

        {result.error && (
          <div
            role="alert"
            className="rounded-[var(--r-md)] border border-status-cancelled bg-status-cancelled-soft p-4 text-sm text-status-cancelled"
          >
            <p className="font-semibold">Fonte de faturação indisponível</p>
            <p className="mt-1">{result.error}</p>
          </div>
        )}

        {result.truncated && (
          <p className="rounded-[var(--r-md)] border border-border bg-surface-2 p-3 text-xs text-muted">
            O limite da consulta foi atingido; os indicadores refletem apenas as
            ordens carregadas.
          </p>
        )}

        <section
          aria-label="Indicadores da faturação da oficina"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          <KpiCard
            label="OS concluídas"
            value={result.data.length}
            semantic="primary"
            icon={<FileCheck2 aria-hidden="true" className="h-5 w-5" />}
          />
          <KpiCard
            label="A processar"
            value={pending.length}
            semantic="warning"
            icon={<Clock3 aria-hidden="true" className="h-5 w-5" />}
          />
          <KpiCard
            label="Rascunhos fiscais"
            value={drafts.length}
            semantic="info"
            icon={<FileText aria-hidden="true" className="h-5 w-5" />}
          />
          <KpiCard
            label="Falhas"
            value={failures.length}
            semantic={failures.length ? "error" : "success"}
            icon={<AlertTriangle aria-hidden="true" className="h-5 w-5" />}
          />
        </section>

        <p className="text-xs text-muted">
          Custo real reconciliado das OS carregadas:{" "}
          <span className="font-mono font-semibold tabular-nums text-ink">
            {money.format(reconciledCost)} MT
          </span>
          . Este valor não é apresentado como faturação emitida.
        </p>

        <section className="overflow-hidden rounded-[var(--r-lg)] border border-border bg-surface shadow-card">
          <div className="border-b border-border px-4 py-4 sm:px-6">
            <h2 className="text-base font-semibold text-ink">
              Ordens no ciclo fiscal
            </h2>
            <p className="mt-1 text-xs text-muted">
              A emissão e a repetição de falhas são executadas no detalhe da OS,
              onde existem os gates operacionais completos.
            </p>
          </div>
          {result.data.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <p className="text-sm font-medium text-ink">
                Nenhuma OS concluída
              </p>
              <p className="mt-1 text-xs text-muted">
                O fecho após QC alimentará este pipeline.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="bg-surface-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  <tr>
                    <th className="px-4 py-3 sm:px-6">Ordem</th>
                    <th className="px-4 py-3">Viatura</th>
                    <th className="px-4 py-3">Fecho</th>
                    <th className="px-4 py-3 text-right">Custo real</th>
                    <th className="px-4 py-3">Estado fiscal</th>
                    <th className="px-4 py-3 text-right sm:px-6">Ação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {result.data.map((order) => {
                    const vehicle = vehicleById.get(order.vehicle_id);
                    return (
                      <tr
                        key={order.id}
                        className="transition-colors hover:bg-surface-2"
                      >
                        <td className="px-4 py-3 font-mono font-semibold tabular-nums text-ink sm:px-6">
                          {order.work_order_number}
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-ink">
                            {vehicle?.plate ?? order.vehicle_id}
                          </p>
                          {vehicle && (
                            <p className="text-xs text-muted">
                              {vehicle.brand} {vehicle.model}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {order.closed_at
                            ? new Date(order.closed_at).toLocaleString("pt-MZ")
                            : "Sem data de fecho"}
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums text-ink">
                          {order.actual_cost === null
                            ? "Não reconciliado"
                            : `${money.format(order.actual_cost)} MT`}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge
                            status={order.billing_status ?? "pending"}
                          />
                          {order.billing_error && (
                            <p className="mt-1 max-w-xs text-xs text-status-cancelled">
                              {order.billing_error}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right sm:px-6">
                          <Link
                            href={`/oficina/ordens-servico/${order.id}`}
                            className="font-semibold text-rotas-600 underline-offset-4 hover:underline"
                          >
                            Abrir gate fiscal
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </SidebarLayout>
  );
}
