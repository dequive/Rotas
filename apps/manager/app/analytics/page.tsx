"use client";

import { useEffect, useState } from "react";
import { BarChart2, Fuel, TrendingUp, Truck } from "lucide-react";
import { SidebarLayout } from "../components/SidebarLayout";
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
  getFleetKpis,
  getDocumentExpiry,
  type FleetKpis,
  type DocumentExpiryItem,
  type DocumentExpiryResponse,
} from "../lib/analytics-api";

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
  const [kpis, setKpis] = useState<FleetKpis | null>(null);
  const [expiry, setExpiry] = useState<DocumentExpiryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const bounds = getPeriodBounds(period, customStart, customEnd);
    if (!bounds) return;
    setLoading(true);
    setError(null);
    Promise.all([
      getFleetKpis({ periodStart: bounds.start, periodEnd: bounds.end }),
      getDocumentExpiry(),
    ])
      .then(([kpiData, expiryData]) => {
        setKpis(kpiData);
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
    kpis && Object.keys(kpis.costPerKm).length > 0
      ? Object.values(kpis.costPerKm).reduce((a, b) => a + b, 0) /
        Object.values(kpis.costPerKm).length
      : null;

  return (
    <SidebarLayout active="analytics">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-[26px] font-extrabold text-ink">Análise de Frota</h1>
        <p className="text-muted text-sm mt-1">
          Indicadores de desempenho e alertas de documentação
        </p>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <Select value={period} onValueChange={(v) => setPeriod(v as PeriodPreset)}>
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
              className="border border-line rounded-md px-3 py-2 text-sm bg-panel text-ink"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
            />
            <input
              type="date"
              aria-label="Até"
              className="border border-line rounded-md px-3 py-2 text-sm bg-panel text-ink"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
            />
          </>
        )}
      </div>

      {error && <p className="text-red text-sm mb-4">{error}</p>}

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
          value={kpis ? `${kpis.fleetUtilization.toFixed(1)}%` : "—"}
        />
        <KpiCard
          title="Consumo L/100 km"
          icon={<Fuel className="w-4 h-4 text-blue" />}
          loading={loading}
          value={kpis ? `${kpis.lPer100Km.toFixed(1)} L` : "—"}
        />
        <KpiCard
          title="Viagens concluídas"
          icon={<BarChart2 className="w-4 h-4 text-blue" />}
          loading={loading}
          value={kpis?.tripsCompleted?.toString() ?? "—"}
        />
      </div>

      {/* Driver summary table */}
      <section className="mb-8">
        <h2 className="text-[21px] font-extrabold text-ink mb-4">Resumo por Motorista</h2>
        <div className="bg-panel border border-line rounded-lg overflow-hidden">
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
              ) : kpis && kpis.driverSummary.length > 0 ? (
                kpis.driverSummary.map((row) => (
                  <TableRow key={row.driverId}>
                    <TableCell className="font-medium">{row.driverName}</TableCell>
                    <TableCell className="text-right">{row.tripsCount}</TableCell>
                    <TableCell className="text-right">
                      {row.totalKm.toLocaleString("pt-MZ")} km
                    </TableCell>
                    <TableCell className="text-right">
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
          <p className="text-[26px] font-extrabold text-ink">{value}</p>
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
    if (severity === "urgent") return "bg-[#fee4e2] text-red border border-red/20";
    return "bg-orange/10 text-orange border border-orange/30";
  }

  return (
    <section>
      <h2 className="text-[21px] font-extrabold text-ink mb-4">Documentos a Vencer</h2>
      {loading ? (
        <Skeleton className="h-32 w-full" />
      ) : sorted.length === 0 ? (
        <div className="bg-panel border border-line rounded-lg p-8 text-center">
          <p className="font-bold text-ink mb-1">Sem documentos a vencer</p>
          <p className="text-muted text-sm">
            Todos os documentos de viaturas e motoristas estão válidos por mais de 30 dias.
          </p>
        </div>
      ) : (
        <div className="bg-panel border border-line rounded-lg overflow-hidden">
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
