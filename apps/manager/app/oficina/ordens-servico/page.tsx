import {
  CheckCircle2,
  Clock,
  Loader2,
  Plus,
  Search,
  Wrench,
} from "lucide-react";
import Link from "next/link";

import { SidebarLayout } from "../../components/SidebarLayout";
import { requireSession } from "../../lib/auth";
import { loadWorkOrders } from "../../lib/workshop-api";

const STATUS_MAP: Record<string, { label: string; classes: string; icon: typeof Clock }> = {
  draft: {
    label: "Rascunho",
    classes: "bg-muted text-muted-foreground border border-border",
    icon: Clock,
  },
  open: {
    label: "Aberta",
    classes: "bg-blue-500/10 text-blue-500 border border-blue-500/20",
    icon: Clock,
  },
  approved: {
    label: "Aprovada",
    classes: "bg-indigo-500/10 text-indigo-500 border border-indigo-500/20",
    icon: Clock,
  },
  in_progress: {
    label: "Em Execução",
    classes: "bg-amber-500/10 text-amber-500 border border-amber-500/20",
    icon: Loader2,
  },
  quality_check: {
    label: "Controlo Qualidade",
    classes: "bg-purple-500/10 text-purple-500 border border-purple-500/20",
    icon: CheckCircle2,
  },
  closed: {
    label: "Concluída",
    classes: "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20",
    icon: CheckCircle2,
  },
};

function formatMZN(value: number | null) {
  if (value === null) return "—";
  return new Intl.NumberFormat("pt-MZ", {
    style: "decimal",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export default async function WorkshopWorkOrdersPage() {
  await requireSession();
  const result = await loadWorkOrders();

  const activeCount = result.data.filter(
    (wo) => wo.status !== "closed" && wo.status !== "draft",
  ).length;
  const closedCount = result.data.filter((wo) => wo.status === "closed").length;

  return (
    <SidebarLayout active="os-oficina">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Ordens de Serviço
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Gestão de ordens de trabalho da oficina — criação, execução e encerramento.
            </p>
          </div>
          <Link
            href="/oficina/orcamentos"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" /> Via Orçamento
          </Link>
        </div>

        {/* KPI bar */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Total OS
              </span>
              <Wrench className="h-5 w-5 text-indigo-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">{result.data.length}</div>
          </div>
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Em Curso
              </span>
              <Loader2 className="h-5 w-5 text-amber-500" />
            </div>
            <div className="text-2xl font-bold text-amber-600">{activeCount}</div>
          </div>
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Concluídas
              </span>
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            </div>
            <div className="text-2xl font-bold text-emerald-600">{closedCount}</div>
          </div>
        </div>

        {/* Error banner */}
        {result.error && (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 px-4 py-3 text-sm text-rose-500">
            {result.error}
          </div>
        )}

        {/* Work Orders Table */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
            <h2 className="text-base font-semibold text-foreground">
              Todas as Ordens de Serviço
            </h2>
            <div className="relative max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Pesquisar por nº OS ou viatura..."
                className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">Nº OS</th>
                  <th className="px-6 py-3">Trabalho Previsto</th>
                  <th className="px-6 py-3 text-right">Custo Est. (MT)</th>
                  <th className="px-6 py-3 text-right">Custo Real (MT)</th>
                  <th className="px-6 py-3">Estado</th>
                  <th className="px-6 py-3">Criada</th>
                  <th className="px-6 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {result.data.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground">
                      <Wrench className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                      <p className="text-sm">Nenhuma ordem de serviço encontrada.</p>
                    </td>
                  </tr>
                )}
                {result.data.map((wo) => {
                  const statusInfo = STATUS_MAP[wo.status] ?? STATUS_MAP.open;
                  const StatusIcon = statusInfo.icon;
                  return (
                    <tr key={wo.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-6 py-4 font-mono font-medium text-foreground">
                        {wo.work_order_number}
                      </td>
                      <td className="px-6 py-4 text-muted-foreground max-w-xs truncate">
                        {wo.planned_work}
                      </td>
                      <td className="px-6 py-4 font-mono text-right text-muted-foreground">
                        {formatMZN(wo.estimated_cost)}
                      </td>
                      <td className="px-6 py-4 font-mono text-right font-semibold text-foreground">
                        {formatMZN(wo.actual_cost)}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${statusInfo.classes}`}
                        >
                          <StatusIcon className="h-3 w-3" />
                          {statusInfo.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-muted-foreground text-xs">
                        {new Date(wo.created_at).toLocaleDateString("pt-MZ")}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          href={`/oficina/ordens-servico/${wo.id}`}
                          className="text-xs font-medium text-primary hover:underline"
                        >
                          Detalhes
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
