import {
  CheckCircle2,
  Clock3,
  FileText,
  Plus,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import Link from "next/link";

import { SidebarLayout } from "../components/SidebarLayout";
import { KpiCard } from "../components/ui/KpiCard";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";
import { requireSession } from "../lib/auth";
import { loadVehicles } from "../lib/vehicles-api";
import {
  loadReceptions,
  loadWarrantiesResult,
  loadWorkOrders,
} from "../lib/workshop-api";

const secondaryAction =
  "inline-flex h-10 items-center justify-center gap-2 rounded-[var(--r-md)] border border-border bg-surface px-4 text-sm font-semibold text-ink shadow-design-sm transition-colors hover:border-border-strong hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2";
const accentAction =
  "inline-flex h-10 items-center justify-center gap-2 rounded-[var(--r-md)] border border-accent-action-600 bg-accent-action-600 px-4 text-sm font-semibold text-white shadow-design-sm transition-colors hover:border-accent-action-500 hover:bg-accent-action-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2";

export default async function WorkshopDashboardPage() {
  await requireSession();

  const [receptionsResult, workOrdersResult, warrantiesResult, vehicles] =
    await Promise.all([
      loadReceptions(),
      loadWorkOrders(),
      loadWarrantiesResult(),
      loadVehicles(),
    ]);

  const vehicleById = new Map(vehicles.map((vehicle) => [vehicle.id, vehicle]));
  const activeReceptions = receptionsResult.data.filter(
    (reception) => !["delivered", "returned_no_service"].includes(reception.status),
  );
  const inRepair = workOrdersResult.data.filter((order) =>
    ["open", "in_progress"].includes(order.status),
  );
  const readyForDelivery = receptionsResult.data.filter(
    (reception) => reception.status === "ready",
  );
  const activeWarranties = warrantiesResult.data.filter(
    (warranty) => warranty.status.toLowerCase() === "active",
  );
  const errors = [
    receptionsResult.error,
    workOrdersResult.error,
    warrantiesResult.error,
  ].filter((error): error is string => Boolean(error));
  const isTruncated =
    receptionsResult.truncated ||
    workOrdersResult.truncated ||
    warrantiesResult.truncated;

  return (
    <SidebarLayout active="recepcao">
      <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6">
        <PageHeader
          eyebrow="Oficina Auto"
          title="Operação da oficina"
          description="Receções, intervenções, entrega e garantias com dados do tenant autenticado."
          actions={
            <>
              <Link href="/oficina/orcamentos" className={secondaryAction}>
                <FileText aria-hidden="true" className="h-4 w-4" />
                Orçamentos
              </Link>
              <Link href="/oficina/recepcao/nova" className={accentAction}>
                <Plus aria-hidden="true" className="h-4 w-4" />
                Novo check-in
              </Link>
            </>
          }
        />

        {errors.length > 0 && (
          <div
            role="alert"
            className="rounded-[var(--r-md)] border border-status-cancelled bg-status-cancelled-soft p-4 text-sm text-status-cancelled"
          >
            <p className="font-semibold">Os indicadores estão incompletos.</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </div>
        )}

        {isTruncated && (
          <p className="rounded-[var(--r-md)] border border-border bg-surface-2 px-4 py-3 text-xs text-muted">
            A vista atingiu o limite de paginação de uma das fontes. Os totais
            apresentados correspondem apenas aos registos carregados.
          </p>
        )}

        <section
          aria-label="Indicadores da oficina"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          <KpiCard
            label="Em receção"
            value={activeReceptions.filter((item) => item.status === "received").length}
            semantic="info"
            icon={<Clock3 aria-hidden="true" className="h-5 w-5" />}
          />
          <KpiCard
            label="Em reparação"
            value={inRepair.length}
            semantic="accent"
            icon={<Wrench aria-hidden="true" className="h-5 w-5" />}
          />
          <KpiCard
            label="Prontas para entrega"
            value={readyForDelivery.length}
            semantic="success"
            icon={<CheckCircle2 aria-hidden="true" className="h-5 w-5" />}
          />
          <KpiCard
            label="Garantias ativas"
            value={activeWarranties.length}
            semantic="primary"
            icon={<ShieldCheck aria-hidden="true" className="h-5 w-5" />}
          />
        </section>

        <section className="overflow-hidden rounded-[var(--r-lg)] border border-border bg-surface shadow-card">
          <div className="flex flex-col gap-1 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <h2 className="text-base font-semibold text-ink">
                Viaturas na oficina
              </h2>
              <p className="text-xs text-muted">
                Check-ins ainda não entregues nem devolvidos sem serviço.
              </p>
            </div>
            <span className="font-mono text-xs tabular-nums text-muted">
              {activeReceptions.length} registo(s)
            </span>
          </div>

          {activeReceptions.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <p className="text-sm font-medium text-ink">
                Nenhuma viatura ativa na oficina
              </p>
              <p className="mt-1 text-xs text-muted">
                Os novos check-ins aparecerão aqui após confirmação pela API.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="bg-surface-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  <tr>
                    <th className="px-4 py-3 sm:px-6">Receção</th>
                    <th className="px-4 py-3">Viatura</th>
                    <th className="px-4 py-3">Entrada</th>
                    <th className="px-4 py-3">Odómetro</th>
                    <th className="px-4 py-3">Estado</th>
                    <th className="px-4 py-3 text-right sm:px-6">
                      Ação
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {activeReceptions.map((reception) => {
                    const vehicle = vehicleById.get(reception.vehicle_id);
                    return (
                      <tr
                        key={reception.id}
                        className="transition-colors hover:bg-surface-2"
                      >
                        <td className="px-4 py-3 font-mono font-semibold tabular-nums text-ink sm:px-6">
                          {reception.reception_number}
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-ink">
                            {vehicle?.plate ?? "Viatura sem matrícula resolvida"}
                          </p>
                          <p className="text-xs text-muted">
                            {vehicle
                              ? `${vehicle.brand} ${vehicle.model}`.trim()
                              : reception.vehicle_id}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {new Date(reception.received_at).toLocaleString("pt-MZ")}
                        </td>
                        <td className="px-4 py-3 font-mono tabular-nums text-ink">
                          {reception.odometer_at_reception.toLocaleString("pt-MZ")} km
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={reception.status} />
                        </td>
                        <td className="px-4 py-3 text-right sm:px-6">
                          <Link
                            href={`/oficina/recepcao/${reception.id}`}
                            className="font-semibold text-rotas-600 underline-offset-4 hover:underline"
                          >
                            Abrir ficha
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
