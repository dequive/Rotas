import {
  ArrowDown,
  ArrowUp,
  BarChart2,
  Clock,
  DollarSign,
  Minus,
  TrendingUp,
  Wrench,
} from "lucide-react";

import { SidebarLayout } from "../../components/SidebarLayout";
import { requireSession } from "../../lib/auth";
import {
  getWorkshopProfitabilitySummary,
  ProfitabilitySummaryItem,
} from "../../lib/workshop-api";

/**
 * Workshop Profitability & BI Report Page.
 *
 * Consumes GET /api/v1/workshop/profitability/summary:
 * - Direct FK-based confirmed revenue (BillingItem → issued/paid BillingDocument)
 * - Projected revenue pipeline for unbilled in-progress Work Orders
 * - TaskLaborLog (hourly rate) + MaintenancePartUsed (WACC unit cost) total costs
 * - Strict Decimal precision and multi-tenant isolation
 */

function formatMZN(value: number) {
  return new Intl.NumberFormat("pt-MZ", {
    style: "decimal",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}
export default async function WorkshopProfitabilityPage() {
  await requireSession();

  const report = await getWorkshopProfitabilitySummary();

  const summary = report?.summary ?? {
    confirmed_revenue: 0,
    projected_revenue: 0,
    total_labor_cost: 0,
    total_parts_cost: 0,
    total_cost: 0,
    confirmed_gross_profit: 0,
    confirmed_gross_margin_pct: 0,
    negative_margin_count: 0,
    total_work_orders: 0,
  };

  const workOrders: ProfitabilitySummaryItem[] = report?.work_orders ?? [];

  return (
    <SidebarLayout active="rentabilidade-oficina">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="border-b border-border pb-5">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Rentabilidade &amp; BI da Oficina
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Margem bruta por Ordem de Serviço — receita faturada confirmada vs. pipeline e custos diretos (mão de obra + peças).
          </p>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Receita Faturada Confirmada */}
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Receita Confirmada
              </span>
              <DollarSign className="h-5 w-5 text-amber" />
            </div>
            <div className="text-2xl font-bold text-foreground">
              {formatMZN(summary.confirmed_revenue)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
            <p className="text-xs text-muted-foreground">Faturas emitidas / pagas</p>
          </div>

          {/* Pipeline em Curso */}
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Pipeline em Curso
              </span>
              <Clock className="h-5 w-5 text-blue-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">
              {formatMZN(summary.projected_revenue)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
            <p className="text-xs text-muted-foreground">Estimativa OSs não faturadas</p>
          </div>

          {/* Custo Total */}
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Custo Total
              </span>
              <Wrench className="h-5 w-5 text-amber-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">
              {formatMZN(summary.total_cost)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
            <p className="text-xs text-muted-foreground">MO ({formatMZN(summary.total_labor_cost)}) + Peças ({formatMZN(summary.total_parts_cost)})</p>
          </div>

          {/* Margem Bruta Confirmada */}
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Margem Bruta
              </span>
              <TrendingUp className="h-5 w-5 text-emerald-500" />
            </div>
            <div
              className={`text-2xl font-bold ${summary.confirmed_gross_profit >= 0 ? "text-emerald-600" : "text-rose-600"}`}
            >
              {formatMZN(summary.confirmed_gross_profit)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Média: {summary.confirmed_gross_margin_pct.toFixed(1)}%
            </p>
          </div>

          {/* OS com Prejuízo */}
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                OS com Prejuízo
              </span>
              <BarChart2 className="h-5 w-5 text-rose-500" />
            </div>
            <div className="text-2xl font-bold text-rose-600">{summary.negative_margin_count}</div>
            <p className="text-xs text-muted-foreground">Margem negativa — atenção</p>
          </div>
        </div>

        {/* Profitability Table */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between">
            <h2 className="text-base font-semibold text-foreground">
              Detalhe por Ordem de Serviço ({workOrders.length})
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">OS</th>
                  <th className="px-6 py-3">Cliente / Viatura</th>
                  <th className="px-6 py-3 text-right">Receita Confirmada</th>
                  <th className="px-6 py-3 text-right">Pipeline</th>
                  <th className="px-6 py-3 text-right">Mão de Obra</th>
                  <th className="px-6 py-3 text-right">Peças</th>
                  <th className="px-6 py-3 text-right">Custo Total</th>
                  <th className="px-6 py-3 text-right">Margem (MT)</th>
                  <th className="px-6 py-3 text-right">Margem (%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {workOrders.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-6 py-8 text-center text-muted-foreground">
                      Nenhuma Ordem de Serviço registada nesta oficina.
                    </td>
                  </tr>
                ) : (
                  workOrders.map((row) => {
                    const isNegative = !row.is_profitable;
                    return (
                      <tr key={row.work_order_id} className="hover:bg-muted/30 transition-colors">
                        <td className="px-6 py-4 font-mono font-medium text-foreground">
                          {row.work_order_number}
                        </td>
                        <td className="px-6 py-4">
                          <div className="font-medium text-foreground">{row.client_name}</div>
                          <div className="text-xs text-muted-foreground">{row.vehicle_name}</div>
                        </td>
                        <td className="px-6 py-4 font-mono text-right text-foreground">
                          {formatMZN(row.confirmed_revenue)}
                        </td>
                        <td className="px-6 py-4 font-mono text-right text-muted-foreground">
                          {formatMZN(row.projected_revenue)}
                        </td>
                        <td className="px-6 py-4 font-mono text-right text-muted-foreground">
                          {formatMZN(row.total_labor_cost)}
                        </td>
                        <td className="px-6 py-4 font-mono text-right text-muted-foreground">
                          {formatMZN(row.total_parts_cost)}
                        </td>
                        <td className="px-6 py-4 font-mono text-right text-foreground">
                          {formatMZN(row.total_cost)}
                        </td>
                        <td
                          className={`px-6 py-4 font-mono font-semibold text-right ${
                            isNegative ? "text-rose-600" : "text-emerald-600"
                          }`}
                        >
                          <span className="inline-flex items-center gap-1">
                            {isNegative ? (
                              <ArrowDown className="h-3.5 w-3.5" />
                            ) : row.margin_mzn > 0 ? (
                              <ArrowUp className="h-3.5 w-3.5" />
                            ) : (
                              <Minus className="h-3.5 w-3.5" />
                            )}
                            {formatMZN(Math.abs(row.margin_mzn))}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold font-mono ${
                              isNegative
                                ? "bg-rose-500/10 text-rose-600 border border-rose-500/20"
                                : row.margin_pct >= 30
                                  ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                                  : "bg-amber-500/10 text-amber-600 border border-amber-500/20"
                            }`}
                          >
                            {row.margin_pct.toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
              {/* Totals row */}
              {workOrders.length > 0 && (
                <tfoot>
                  <tr className="bg-muted/30 font-semibold text-foreground">
                    <td className="px-6 py-3" colSpan={2}>
                      TOTAL
                    </td>
                    <td className="px-6 py-3 font-mono text-right">{formatMZN(summary.confirmed_revenue)}</td>
                    <td className="px-6 py-3 font-mono text-right text-muted-foreground">{formatMZN(summary.projected_revenue)}</td>
                    <td className="px-6 py-3 font-mono text-right text-muted-foreground">
                      {formatMZN(summary.total_labor_cost)}
                    </td>
                    <td className="px-6 py-3 font-mono text-right text-muted-foreground">
                      {formatMZN(summary.total_parts_cost)}
                    </td>
                    <td className="px-6 py-3 font-mono text-right">{formatMZN(summary.total_cost)}</td>
                    <td
                      className={`px-6 py-3 font-mono text-right ${
                        summary.confirmed_gross_profit >= 0 ? "text-emerald-600" : "text-rose-600"
                      }`}
                    >
                      {formatMZN(summary.confirmed_gross_profit)}
                    </td>
                    <td className="px-6 py-3 font-mono text-right">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                          summary.confirmed_gross_margin_pct >= 30
                            ? "bg-emerald-500/10 text-emerald-600"
                            : summary.confirmed_gross_margin_pct >= 0
                              ? "bg-amber-500/10 text-amber-600"
                              : "bg-rose-500/10 text-rose-600"
                        }`}
                      >
                        {summary.confirmed_gross_margin_pct.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
