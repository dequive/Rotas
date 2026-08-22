"use client";

import { useEffect, useState } from "react";
import { BarChart2, Fuel, TrendingUp, Truck } from "lucide-react";
import { SidebarLayout } from "../components/SidebarLayout";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getAnalyticsDashboard,
  getDocumentExpiry,
  type AnalyticsDashboard,
  type DocumentExpiryItem,
  type DocumentExpiryResponse,
} from "../lib/analytics-api";
import ExportButtons from "./ExportButtons";

type PeriodPreset = "este_mes" | "ultimos_3_meses" | "personalizado";

function getPeriodBounds(
  preset: PeriodPreset,
  customStart?: string,
  customEnd?: string,
): { start: string; end: string } | null {
  const now = new Date();
  if (preset === "este_mes") {
    const start = new Date(Date.UTC(now.getFullYear(), now.getMonth(), 1));
    return { start: start.toISOString(), end: now.toISOString() };
  }
  if (preset === "ultimos_3_meses") {
    const start = new Date(now);
    start.setDate(start.getDate() - 90);
    return { start: start.toISOString(), end: now.toISOString() };
  }
  if (customStart && customEnd) {
    return {
      start: new Date(customStart).toISOString(),
      end: new Date(customEnd).toISOString(),
    };
  }
  return null;
}

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<PeriodPreset>("este_mes");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [dashboard, setDashboard] = useState<AnalyticsDashboard | null>(null);
  const [expiry, setExpiry] = useState<DocumentExpiryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Derived current month for export buttons
  const currentMonth = new Date().toISOString().slice(0, 7); // YYYY-MM

  useEffect(() => {
    const bounds = getPeriodBounds(period, customStart, customEnd);
    if (!bounds) return;
    setLoading(true);
    setError(null);
    Promise.all([
      getAnalyticsDashboard({ periodStart: bounds.start, periodEnd: bounds.end }),
      getDocumentExpiry(),
    ])
      .then(([dashData, expiryData]) => {
        setDashboard(dashData);
        setExpiry(expiryData);
      })
      .catch(() =>
        setError(
          "Não foi possível carregar os dados. Atualize a página ou contacte o suporte se o problema persistir.",
        ),
      )
      .finally(() => setLoading(false));
  }, [period, customStart, customEnd]);

  const avgCostPerKm =
    dashboard && Object.keys(dashboard.costPerKm).length > 0
      ? Object.values(dashboard.costPerKm).reduce((a, b) => a + b, 0) /
        Object.values(dashboard.costPerKm).length
      : null;

  return (
    <SidebarLayout active="analytics">
      <PageHeader
        eyebrow="Financeiro"
        title="Analytics"
        description="Indicadores de desempenho e alertas de documentação"
      />

      {/* Filter bar + Export buttons */}
      <div className="flex items-center justify-between gap-3 mb-6 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          <Select
            value={period}
            onValueChange={(v: string) => setPeriod(v as PeriodPreset)}
          >
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Período" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="este_mes">Este mês</SelectItem>
              <SelectItem value="ultimos_3_meses">Últimos 3 meses</SelectItem>
              <SelectItem value="personalizado">Personalizado</SelectItem>
            </SelectContent>
          </Select>
          {period === "personalizado" && (
            <>
              <input
                type="date"
                aria-label="De"
                className="border border-border rounded-md px-3 py-2 text-sm bg-surface text-ink"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
              />
              <input
                type="date"
                aria-label="Até"
                className="border border-border rounded-md px-3 py-2 text-sm bg-surface text-ink"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
              />
            </>
          )}
        </div>
        <ExportButtons currentMonth={currentMonth} />
      </div>

      {error && <p className="text-error text-sm mb-4">{error}</p>}

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard
          title="Custo médio / km"
          icon={<TrendingUp className="w-4 h-4 text-blue" />}
          loading={loading}
          value={avgCostPerKm !== null ? `${avgCostPerKm.toFixed(2)} MZN` : "—"}
        />
        <KpiCard
          title="Utilização de frota"
          icon={<Truck className="w-4 h-4 text-blue" />}
          loading={loading}
          value={dashboard ? `${dashboard.fleetUtilization.toFixed(1)}%` : "—"}
        />
        <KpiCard
          title="Consumo L/100 km"
          icon={<Fuel className="w-4 h-4 text-blue" />}
          loading={loading}
          value={dashboard ? `${dashboard.lPer100Km.toFixed(1)} L` : "—"}
        />
        <KpiCard
          title="Viagens concluídas"
          icon={<BarChart2 className="w-4 h-4 text-blue" />}
          loading={loading}
          value={dashboard?.tripsCompleted?.toString() ?? "—"}
        />
      </div>

      {/* Driver summary table */}
      <section className="mb-8">
        <h2 className="text-[21px] font-extrabold text-ink mb-4">Resumo por Motorista</h2>
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Motorista</TableHead>
                <TableHead className="text-right">Viagens</TableHead>
                <TableHead className="text-right">Km totais</TableHead>
                <TableHead className="text-right">Custo total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={4}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              ) : dashboard && dashboard.driverSummary.length > 0 ? (
                dashboard.driverSummary.map((row) => (
                  <TableRow key={row.driverId}>
                    <TableCell className="font-medium">{row.driverName}</TableCell>
                    <TableCell className="text-right">{row.tripsCount}</TableCell>
                    <TableCell className="text-right">
                      {row.totalKm.toLocaleString("pt-MZ")} km
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {row.totalCost.toLocaleString("pt-MZ", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}{" "}
                      MZN
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-8 text-muted text-sm">
                    Sem dados para o período
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* Route Profitability */}
      <section className="mb-8">
        <h2 className="text-[21px] font-extrabold text-ink mb-4">Rotas mais Rentáveis</h2>
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Origem</TableHead>
                <TableHead>Destino</TableHead>
                <TableHead className="text-right">Viagens</TableHead>
                <TableHead className="text-right">Custo Médio (MZN)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={4}>
                    <Skeleton className="h-5 w-full" />
                  </TableCell>
                </TableRow>
              ) : dashboard && dashboard.route_profitability.length > 0 ? (
                dashboard.route_profitability.map((r, i) => (
                  <TableRow key={i}>
                    <TableCell>{r.origin}</TableCell>
                    <TableCell>{r.destination}</TableCell>
                    <TableCell className="text-right">{r.trip_count}</TableCell>
                    <TableCell className="text-right font-mono">
                      {r.avg_cost.toLocaleString("pt-MZ", { minimumFractionDigits: 2 })}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-6 text-muted text-sm">
                    Sem dados para o período
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* Contract Margins */}
      <section className="mb-8">
        <h2 className="text-[21px] font-extrabold text-ink mb-4">Margens por Contrato</h2>
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Documento</TableHead>
                <TableHead className="text-right">Receita (MZN)</TableHead>
                <TableHead className="text-right">Custo (MZN)</TableHead>
                <TableHead className="text-right">Margem (MZN)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={4}>
                    <Skeleton className="h-5 w-full" />
                  </TableCell>
                </TableRow>
              ) : dashboard && dashboard.contract_margins.length > 0 ? (
                dashboard.contract_margins.map((r, i) => (
                  <TableRow key={r.billing_document_id}>
                    <TableCell className="font-mono text-sm">
                      {r.invoice_number ?? `#${i + 1}`}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {r.total_revenue.toLocaleString("pt-MZ", { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {r.total_cost.toLocaleString("pt-MZ", { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono font-semibold ${r.gross_margin >= 0 ? "text-success" : "text-error"}`}
                    >
                      {r.gross_margin.toLocaleString("pt-MZ", { minimumFractionDigits: 2 })}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-6 text-muted text-sm">
                    Sem dados para o período
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* Delivery NPS */}
      <section className="mb-8">
        <h2 className="text-[21px] font-extrabold text-ink mb-4">NPS de Entrega</h2>
        <div className="bg-surface border border-border rounded-lg p-6 flex items-center gap-6">
          {loading ? (
            <Skeleton className="h-16 w-32" />
          ) : (
            <>
              <p
                className="font-mono text-[48px] font-extrabold leading-none"
                style={{
                  color:
                    dashboard?.delivery_nps == null
                      ? "var(--muted)"
                      : dashboard.delivery_nps >= 70
                        ? "var(--success)"
                        : dashboard.delivery_nps < 50
                          ? "var(--error)"
                          : "var(--warning)",
                }}
              >
                {dashboard?.delivery_nps !== null && dashboard?.delivery_nps !== undefined
                  ? `${dashboard.delivery_nps.toFixed(1)}%`
                  : "—"}
              </p>
              <p className="text-sm text-muted max-w-xs">
                Percentagem de entregas com carga intacta no período seleccionado.
              </p>
            </>
          )}
        </div>
      </section>

      {/* Top Drivers */}
      <section className="mb-8">
        <h2 className="text-[21px] font-extrabold text-ink mb-4">Top Motoristas</h2>
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Motorista</TableHead>
                <TableHead className="text-right">Viagens</TableHead>
                <TableHead className="text-right">Km totais</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={3}>
                    <Skeleton className="h-5 w-full" />
                  </TableCell>
                </TableRow>
              ) : dashboard && dashboard.top_drivers.length > 0 ? (
                dashboard.top_drivers.map((d, i) => (
                  <TableRow key={d.driver_id}>
                    <TableCell className="font-medium">
                      #{i + 1} {d.driver_name ?? "—"}
                    </TableCell>
                    <TableCell className="text-right">{d.trip_count}</TableCell>
                    <TableCell className="text-right font-mono">
                      {d.total_km.toLocaleString("pt-MZ")} km
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={3} className="text-center py-6 text-muted text-sm">
                    Sem dados para o período
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* Document expiry panel */}
      <ExpiryPanel expiry={expiry} loading={loading} />
    </SidebarLayout>
  );
}

function KpiCard({
  title,
  icon,
  loading,
  value,
}: {
  title: string;
  icon: React.ReactNode;
  loading: boolean;
  value: string;
}) {
  return (
    <Card className="border-l-4 border-l-blue">
      <CardHeader className="pb-2 flex flex-row items-center justify-between">
        <CardTitle className="text-sm font-bold text-muted">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <p className="text-[26px] font-extrabold text-ink font-mono">{value}</p>
        )}
      </CardContent>
    </Card>
  );
}

function ExpiryPanel({
  expiry,
  loading,
}: {
  expiry: DocumentExpiryResponse | null;
  loading: boolean;
}) {
  const all = expiry ? [...expiry.vehicles, ...expiry.drivers] : [];
  const sorted = [...all].sort((a, b) => a.daysUntilExpiry - b.daysUntilExpiry);

  function severityClass(severity: DocumentExpiryItem["severity"]) {
    if (severity === "critical") return "bg-red text-white";
    if (severity === "urgent") return "bg-error-bg text-error border border-error-border";
    return "bg-orange/10 text-orange border border-orange/30";
  }

  return (
    <section>
      <h2 className="text-[21px] font-extrabold text-ink mb-4">Documentos a Vencer</h2>
      {loading ? (
        <Skeleton className="h-32 w-full" />
      ) : sorted.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg p-8 text-center">
          <p className="font-bold text-ink mb-1">Sem documentos a vencer</p>
          <p className="text-muted text-sm">
            Todos os documentos de viaturas e motoristas estão válidos por mais de 30 dias.
          </p>
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Entidade</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Documento</TableHead>
                <TableHead>Vence em</TableHead>
                <TableHead>Prazo</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((item, i) => (
                <TableRow key={i}>
                  <TableCell className="font-medium">{item.entityName}</TableCell>
                  <TableCell className="text-muted capitalize">
                    {item.entityType === "vehicle" ? "Viatura" : "Motorista"}
                  </TableCell>
                  <TableCell>{item.documentType}</TableCell>
                  <TableCell>
                    {new Date(item.expiresAt).toLocaleDateString("pt-MZ")}
                  </TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold ${severityClass(item.severity)}`}
                    >
                      Vence em {item.daysUntilExpiry} dias
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}
