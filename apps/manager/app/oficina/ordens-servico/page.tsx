import { CheckCircle2, LoaderCircle, Wrench } from "lucide-react";
import Link from "next/link";

import { DataSourceBadge } from "@/app/components/ui/DataSourceBadge";
import {
  DataTable,
  RotasTableActionsCell,
  RotasTableActionsHeader,
  RotasTableCell,
  RotasTableHeader,
  RotasTableRow,
  TableBody,
  TableHeader,
  TableRow,
} from "@/app/components/ui/DataTable";
import { KpiCard } from "@/app/components/ui/KpiCard";
import { MonoCell } from "@/app/components/ui/MonoCell";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { Button } from "@/components/ui/button";

import { SidebarLayout } from "../../components/SidebarLayout";
import { requireSession } from "../../lib/auth";
import { loadWorkOrders } from "../../lib/workshop-api";
import { WorkOrderFormModal } from "../../manutencao/components/WorkOrderFormModal";

function formatMZN(value: number | null) {
  if (value === null) return "—";
  return new Intl.NumberFormat("pt-MZ", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export default async function WorkshopWorkOrdersPage() {
  await requireSession();
  const result = await loadWorkOrders();

  const activeCount = result.data.filter(
    (workOrder) => !["closed", "draft"].includes(workOrder.status),
  ).length;
  const closedCount = result.data.filter(
    (workOrder) => workOrder.status === "closed",
  ).length;

  return (
    <SidebarLayout active="os-oficina">
      <div className="mx-auto max-w-[1440px] space-y-6">
        <PageHeader
          eyebrow="Oficina Auto"
          title="Ordens de serviço"
          description="Execução, consumo, controlo de qualidade e fecho num único fluxo auditável."
          actions={
            <>
              <Button asChild variant="secondary">
                <Link href="/oficina/orcamentos">Consultar orçamentos</Link>
              </Button>
              <WorkOrderFormModal />
            </>
          }
          meta={
            <DataSourceBadge
              source={result.error ? "unavailable" : "api"}
              message={
                result.error
                  ? "API indisponível. Nenhuma ordem fictícia foi apresentada."
                  : "Dados operacionais obtidos da API da Oficina."
              }
              className="mb-0"
            />
          }
        />

        <section
          aria-label="Resumo das ordens de serviço"
          className="grid grid-cols-1 gap-4 sm:grid-cols-3"
        >
          <KpiCard
            label="Total de OS"
            value={result.data.length}
            semantic="primary"
            icon={<Wrench aria-hidden="true" className="h-5 w-5 text-rotas-500" />}
          />
          <KpiCard
            label="Em curso"
            value={activeCount}
            semantic="success"
            icon={<LoaderCircle aria-hidden="true" className="h-5 w-5 text-status-execution" />}
          />
          <KpiCard
            label="Concluídas"
            value={closedCount}
            semantic="success"
            icon={<CheckCircle2 aria-hidden="true" className="h-5 w-5 text-status-delivered" />}
          />
        </section>

        {result.error && (
          <div
            role="alert"
            className="rounded-[var(--r-md)] border border-error-border bg-error-bg px-4 py-3 text-sm text-error"
          >
            <strong>Não foi possível carregar as ordens de serviço.</strong>{" "}
            {result.error}
          </div>
        )}

        {result.truncated && (
          <div
            role="status"
            className="rounded-[var(--r-md)] border border-warning-border bg-warning-bg px-4 py-3 text-sm text-warning"
          >
            A lista atingiu o limite de 500 registos. Use filtros da API antes de
            tomar decisões sobre o total.
          </div>
        )}

        <section aria-labelledby="work-orders-heading" className="space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 id="work-orders-heading" className="text-xl font-semibold text-ink">
                Todas as ordens
              </h2>
              <p className="mt-1 text-sm text-muted">
                Valores em MZN. Abra uma ordem para executar transições, peças e mão-de-obra.
              </p>
            </div>
            <span className="font-mono text-xs text-muted" aria-live="polite">
              {result.data.length} registo(s)
            </span>
          </div>

          <DataTable className="shadow-card">
            <TableHeader>
              <TableRow>
                <RotasTableHeader>N.º OS</RotasTableHeader>
                <RotasTableHeader>Trabalho previsto</RotasTableHeader>
                <RotasTableHeader className="text-right">Estimado</RotasTableHeader>
                <RotasTableHeader className="text-right">Real</RotasTableHeader>
                <RotasTableHeader>Estado</RotasTableHeader>
                <RotasTableHeader>Criada</RotasTableHeader>
                <RotasTableActionsHeader>
                  <span className="sr-only">Ações</span>
                </RotasTableActionsHeader>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.data.length === 0 ? (
                <RotasTableRow>
                  <RotasTableCell colSpan={7} className="h-32 text-center text-muted">
                    <Wrench aria-hidden="true" className="mx-auto mb-3 h-8 w-8 text-tertiary" />
                    <p className="font-medium text-ink">Sem ordens de serviço</p>
                    <p className="mt-1 text-sm">
                      Quando uma OS real for criada, aparecerá nesta lista.
                    </p>
                  </RotasTableCell>
                </RotasTableRow>
              ) : (
                result.data.map((workOrder) => (
                  <RotasTableRow key={workOrder.id}>
                    <RotasTableCell>
                      <MonoCell className="font-semibold text-ink">
                        {workOrder.work_order_number}
                      </MonoCell>
                    </RotasTableCell>
                    <RotasTableCell className="max-w-sm">
                      <span className="line-clamp-2">{workOrder.planned_work}</span>
                    </RotasTableCell>
                    <RotasTableCell className="text-right">
                      <MonoCell className="text-muted">
                        {formatMZN(workOrder.estimated_cost)} MT
                      </MonoCell>
                    </RotasTableCell>
                    <RotasTableCell className="text-right">
                      <MonoCell className="font-semibold text-ink">
                        {formatMZN(workOrder.actual_cost)} MT
                      </MonoCell>
                    </RotasTableCell>
                    <RotasTableCell>
                      <StatusBadge status={workOrder.status} />
                    </RotasTableCell>
                    <RotasTableCell className="text-xs text-muted">
                      <time dateTime={workOrder.created_at}>
                        {new Date(workOrder.created_at).toLocaleDateString("pt-MZ")}
                      </time>
                    </RotasTableCell>
                    <RotasTableActionsCell>
                      <Button asChild size="sm" variant="ghost">
                        <Link href={`/oficina/ordens-servico/${workOrder.id}`}>
                          Ver detalhes
                        </Link>
                      </Button>
                    </RotasTableActionsCell>
                  </RotasTableRow>
                ))
              )}
            </TableBody>
          </DataTable>
        </section>
      </div>
    </SidebarLayout>
  );
}
