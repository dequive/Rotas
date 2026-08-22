import { AlertTriangle, Clock3, ShieldCheck, ShieldX } from "lucide-react";
import Link from "next/link";

import { SidebarLayout } from "../../components/SidebarLayout";
import { KpiCard } from "../../components/ui/KpiCard";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { requireSession } from "../../lib/auth";
import { loadVehicles } from "../../lib/vehicles-api";
import {
  loadWarrantiesResult,
  loadWorkOrders,
} from "../../lib/workshop-api";

function warrantyTypeLabel(type: string) {
  if (type === "parts") return "Peças";
  if (type === "labor") return "Mão de obra";
  return "Serviço completo";
}

export default async function WorkshopWarrantiesPage() {
  await requireSession();
  const [result, workOrdersResult, vehicles] = await Promise.all([
    loadWarrantiesResult(),
    loadWorkOrders(),
    loadVehicles(),
  ]);
  const vehicleById = new Map(vehicles.map((vehicle) => [vehicle.id, vehicle]));
  const workOrderById = new Map(
    workOrdersResult.data.map((order) => [order.id, order]),
  );
  const now = Date.now();
  const thirtyDays = 30 * 24 * 60 * 60 * 1000;
  const active = result.data.filter(
    (warranty) => warranty.status.toLowerCase() === "active",
  );
  const expiring = active.filter((warranty) => {
    const remaining = new Date(warranty.expires_at).getTime() - now;
    return remaining >= 0 && remaining <= thirtyDays;
  });
  const claimed = result.data.filter(
    (warranty) => warranty.status.toLowerCase() === "claimed",
  );
  const expired = result.data.filter(
    (warranty) =>
      warranty.status.toLowerCase() === "expired" ||
      new Date(warranty.expires_at).getTime() < now,
  );
  const errors = [result.error, workOrdersResult.error].filter(
    (error): error is string => Boolean(error),
  );

  return (
    <SidebarLayout active="garantias">
      <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6">
        <PageHeader
          eyebrow="Oficina Auto"
          title="Garantias"
          description="Coberturas emitidas a partir do serviço executado, com validade por prazo e quilometragem."
        />

        {errors.length > 0 && (
          <div
            role="alert"
            className="rounded-[var(--r-md)] border border-status-cancelled bg-status-cancelled-soft p-4 text-sm text-status-cancelled"
          >
            <p className="font-semibold">A vista está incompleta.</p>
            <ul className="mt-1 list-disc pl-5">
              {errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </div>
        )}

        {(result.truncated || workOrdersResult.truncated) && (
          <p className="rounded-[var(--r-md)] border border-border bg-surface-2 p-3 text-xs text-muted">
            Uma das fontes atingiu o limite de paginação; os totais refletem
            apenas os registos carregados.
          </p>
        )}

        <section
          aria-label="Indicadores de garantia"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          <KpiCard
            label="Ativas"
            value={active.length}
            semantic="success"
            icon={<ShieldCheck aria-hidden="true" className="h-5 w-5" />}
          />
          <KpiCard
            label="A vencer em 30 dias"
            value={expiring.length}
            semantic="warning"
            icon={<Clock3 aria-hidden="true" className="h-5 w-5" />}
          />
          <KpiCard
            label="Acionadas"
            value={claimed.length}
            semantic="info"
            icon={<AlertTriangle aria-hidden="true" className="h-5 w-5" />}
          />
          <KpiCard
            label="Expiradas"
            value={expired.length}
            semantic="default"
            icon={<ShieldX aria-hidden="true" className="h-5 w-5" />}
          />
        </section>

        <section className="overflow-hidden rounded-[var(--r-lg)] border border-border bg-surface shadow-card">
          <div className="border-b border-border px-4 py-4 sm:px-6">
            <h2 className="text-base font-semibold text-ink">
              Coberturas emitidas
            </h2>
            <p className="mt-1 text-xs text-muted">
              Cada garantia permanece ligada à OS e à viatura de origem.
            </p>
          </div>
          {result.data.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <p className="text-sm font-medium text-ink">
                Nenhuma garantia emitida
              </p>
              <p className="mt-1 text-xs text-muted">
                As garantias reais aparecerão aqui após criação pela API.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-left text-sm">
                <thead className="bg-surface-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  <tr>
                    <th className="px-4 py-3 sm:px-6">Viatura</th>
                    <th className="px-4 py-3">Ordem de serviço</th>
                    <th className="px-4 py-3">Cobertura</th>
                    <th className="px-4 py-3">Início</th>
                    <th className="px-4 py-3">Validade</th>
                    <th className="px-4 py-3">Estado</th>
                    <th className="px-4 py-3 text-right sm:px-6">Ação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {result.data.map((warranty) => {
                    const vehicle = vehicleById.get(warranty.vehicle_id);
                    const order = workOrderById.get(warranty.work_order_id);
                    return (
                      <tr
                        key={warranty.id}
                        className="transition-colors hover:bg-surface-2"
                      >
                        <td className="px-4 py-3 sm:px-6">
                          <p className="font-semibold text-ink">
                            {vehicle?.plate ?? warranty.vehicle_id}
                          </p>
                          {vehicle && (
                            <p className="text-xs text-muted">
                              {vehicle.brand} {vehicle.model}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3 font-mono tabular-nums text-ink">
                          {order?.work_order_number ?? warranty.work_order_id}
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-ink">
                            {warrantyTypeLabel(warranty.warranty_type)}
                          </p>
                          <p className="text-xs text-muted">
                            {warranty.duration_months} meses
                            {warranty.duration_km !== null
                              ? ` · ${warranty.duration_km.toLocaleString("pt-MZ")} km`
                              : ""}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {new Date(warranty.starts_at).toLocaleDateString(
                            "pt-MZ",
                          )}
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {new Date(warranty.expires_at).toLocaleDateString(
                            "pt-MZ",
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge
                            status={
                              new Date(warranty.expires_at).getTime() < now
                                ? "expired"
                                : warranty.status
                            }
                          />
                        </td>
                        <td className="px-4 py-3 text-right sm:px-6">
                          <Link
                            href={`/oficina/ordens-servico/${warranty.work_order_id}`}
                            className="font-semibold text-rotas-600 underline-offset-4 hover:underline"
                          >
                            Abrir OS
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
