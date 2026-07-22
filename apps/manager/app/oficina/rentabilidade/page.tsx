import {
  ArrowDown,
  ArrowUp,
  BarChart2,
  DollarSign,
  Minus,
  TrendingUp,
  Wrench,
} from "lucide-react";

import { SidebarLayout } from "../../components/SidebarLayout";
import { requireSession } from "../../lib/auth";

/**
 * Workshop Profitability Report page.
 *
 * Shows gross margin per Work Order using the direct FK-based revenue aggregation
 * (BillingItem.work_order_id → invoice totals) and TaskLaborLog-based cost computation.
 *
 * Data: /api/v1/workshop/work-orders/{id}/profitability
 * Fallback: static demo data while endpoint is wired.
 */

const DEMO_PROFITABILITY = [
  {
    id: "wo-001",
    woNumber: "OS-2026-0044",
    client: "Manuel Silva Construções",
    vehicle: "Toyota Hilux (AFM-849-MC)",
    revenue: 8400,
    laborCost: 2100,
    partsCost: 3200,
    totalCost: 5300,
    margin: 3100,
    marginPct: 36.9,
    status: "closed",
  },
  {
    id: "wo-002",
    woNumber: "OS-2026-0042",
    client: "Transportes Maguezo Lda",
    vehicle: "Mitsubishi Canter (AAB-992-MC)",
    revenue: 15600,
    laborCost: 4800,
    partsCost: 5400,
    totalCost: 10200,
    margin: 5400,
    marginPct: 34.6,
    status: "closed",
  },
  {
    id: "wo-003",
    woNumber: "OS-2026-0040",
    client: "Frota Própria (TMS)",
    vehicle: "Isuzu D-Max (AAG-102-MP)",
    revenue: 4250,
    laborCost: 1800,
    partsCost: 2800,
    totalCost: 4600,
    margin: -350,
    marginPct: -8.2,
    status: "closed",
  },
  {
    id: "wo-004",
    woNumber: "OS-2026-0038",
    client: "Cervejas de Moçambique",
    vehicle: "Volvo FH (ABL-440-MZ)",
    revenue: 22000,
    laborCost: 6200,
    partsCost: 8900,
    totalCost: 15100,
    margin: 6900,
    marginPct: 31.4,
    status: "closed",
  },
];

function formatMZN(value: number) {
  return new Intl.NumberFormat("pt-MZ", {
    style: "decimal",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export default async function WorkshopProfitabilityPage() {
  await requireSession();

  // Aggregates
  const totalRevenue = DEMO_PROFITABILITY.reduce((s, r) => s + r.revenue, 0);
  const totalCost = DEMO_PROFITABILITY.reduce((s, r) => s + r.totalCost, 0);
  const totalMargin = totalRevenue - totalCost;
  const avgMarginPct = totalRevenue > 0 ? (totalMargin / totalRevenue) * 100 : 0;
  const negativeMarginCount = DEMO_PROFITABILITY.filter((r) => r.marginPct < 0).length;

  return (
    <SidebarLayout active="rentabilidade-oficina">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="border-b border-border pb-5">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Rentabilidade da Oficina
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Margem bruta por Ordem de Serviço — receita (faturação) vs. custo (mão de obra + peças).
          </p>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Receita Total
              </span>
              <DollarSign className="h-5 w-5 text-indigo-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">
              {formatMZN(totalRevenue)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Custo Total
              </span>
              <Wrench className="h-5 w-5 text-amber-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">
              {formatMZN(totalCost)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Margem Bruta
              </span>
              <TrendingUp className="h-5 w-5 text-emerald-500" />
            </div>
            <div
              className={`text-2xl font-bold ${totalMargin >= 0 ? "text-emerald-600" : "text-rose-600"}`}
            >
              {formatMZN(totalMargin)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Média: {avgMarginPct.toFixed(1)}%
            </p>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                OS com Prejuízo
              </span>
              <BarChart2 className="h-5 w-5 text-rose-500" />
            </div>
            <div className="text-2xl font-bold text-rose-600">{negativeMarginCount}</div>
            <p className="text-xs text-muted-foreground">Margem negativa — revisão recomendada</p>
          </div>
        </div>

        {/* Profitability Table */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border">
            <h2 className="text-base font-semibold text-foreground">
              Detalhe por Ordem de Serviço
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">OS</th>
                  <th className="px-6 py-3">Cliente / Viatura</th>
                  <th className="px-6 py-3 text-right">Receita (MT)</th>
                  <th className="px-6 py-3 text-right">Mão de Obra</th>
                  <th className="px-6 py-3 text-right">Peças</th>
                  <th className="px-6 py-3 text-right">Custo Total</th>
                  <th className="px-6 py-3 text-right">Margem (MT)</th>
                  <th className="px-6 py-3 text-right">Margem (%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {DEMO_PROFITABILITY.map((row) => {
                  const isNegative = row.marginPct < 0;
                  return (
                    <tr key={row.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-6 py-4 font-mono font-medium text-foreground">
                        {row.woNumber}
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-foreground">{row.client}</div>
                        <div className="text-xs text-muted-foreground">{row.vehicle}</div>
                      </td>
                      <td className="px-6 py-4 font-mono text-right text-foreground">
                        {formatMZN(row.revenue)}
                      </td>
                      <td className="px-6 py-4 font-mono text-right text-muted-foreground">
                        {formatMZN(row.laborCost)}
                      </td>
                      <td className="px-6 py-4 font-mono text-right text-muted-foreground">
                        {formatMZN(row.partsCost)}
                      </td>
                      <td className="px-6 py-4 font-mono text-right text-foreground">
                        {formatMZN(row.totalCost)}
                      </td>
                      <td
                        className={`px-6 py-4 font-mono font-semibold text-right ${
                          isNegative ? "text-rose-600" : "text-emerald-600"
                        }`}
                      >
                        <span className="inline-flex items-center gap-1">
                          {isNegative ? (
                            <ArrowDown className="h-3.5 w-3.5" />
                          ) : row.margin > 0 ? (
                            <ArrowUp className="h-3.5 w-3.5" />
                          ) : (
                            <Minus className="h-3.5 w-3.5" />
                          )}
                          {formatMZN(Math.abs(row.margin))}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold font-mono ${
                            isNegative
                              ? "bg-rose-500/10 text-rose-600 border border-rose-500/20"
                              : row.marginPct >= 30
                                ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                                : "bg-amber-500/10 text-amber-600 border border-amber-500/20"
                          }`}
                        >
                          {row.marginPct.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              {/* Totals row */}
              <tfoot>
                <tr className="bg-muted/30 font-semibold text-foreground">
                  <td className="px-6 py-3" colSpan={2}>
                    TOTAL
                  </td>
                  <td className="px-6 py-3 font-mono text-right">{formatMZN(totalRevenue)}</td>
                  <td className="px-6 py-3 font-mono text-right text-muted-foreground">
                    {formatMZN(DEMO_PROFITABILITY.reduce((s, r) => s + r.laborCost, 0))}
                  </td>
                  <td className="px-6 py-3 font-mono text-right text-muted-foreground">
                    {formatMZN(DEMO_PROFITABILITY.reduce((s, r) => s + r.partsCost, 0))}
                  </td>
                  <td className="px-6 py-3 font-mono text-right">{formatMZN(totalCost)}</td>
                  <td
                    className={`px-6 py-3 font-mono text-right ${
                      totalMargin >= 0 ? "text-emerald-600" : "text-rose-600"
                    }`}
                  >
                    {formatMZN(totalMargin)}
                  </td>
                  <td className="px-6 py-3 font-mono text-right">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                        avgMarginPct >= 30
                          ? "bg-emerald-500/10 text-emerald-600"
                          : avgMarginPct >= 0
                            ? "bg-amber-500/10 text-amber-600"
                            : "bg-rose-500/10 text-rose-600"
                      }`}
                    >
                      {avgMarginPct.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
