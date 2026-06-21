import Link from "next/link";
import { requireSession } from "@/app/lib/auth";
import { apiFetch } from "@/app/lib/api";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { SectionHeader } from "@/app/components/ui/SectionHeader";
import { KpiCard } from "@/app/components/ui/KpiCard";
import {
  DataTable,
  RotasTableHeader,
  RotasTableRow,
  RotasTableCell,
  TableBody,
  TableHeader,
  TableRow,
} from "@/app/components/ui/DataTable";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ArSummary {
  current: string;
  "1_30": string;
  "31_60": string;
  "61_90": string;
  over_90: string;
  total_ar: string;
  currency: string;
  as_of: string;
}

interface TopDebtor {
  client_id: string;
  client_name: string;
  outstanding: string;
  worst_bucket: "current" | "1_30" | "31_60" | "61_90" | "over_90";
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatMzn(val: string | number | null | undefined): string {
  if (val == null) return "—";
  const n = Number(val);
  if (isNaN(n)) return "—";
  return n.toLocaleString("pt-MZ", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// Bucket display config
interface BucketConfig {
  key: keyof Pick<ArSummary, "current" | "1_30" | "31_60" | "61_90" | "over_90">;
  label: string;
  containerClass: string;
  textClass: string;
}

const BUCKETS: BucketConfig[] = [
  {
    key: "current",
    label: "Corrente",
    containerClass: "bg-surface-2 border-border",
    textClass: "text-ink",
  },
  {
    key: "1_30",
    label: "1 – 30 d",
    containerClass: "bg-surface-2 border-border",
    textClass: "text-ink",
  },
  {
    key: "31_60",
    label: "31 – 60 d",
    containerClass: "bg-warning-bg border-warning-border",
    textClass: "text-warning",
  },
  {
    key: "61_90",
    label: "61 – 90 d",
    containerClass: "bg-error-bg border-error-border",
    textClass: "text-error",
  },
  {
    key: "over_90",
    label: "+ 90 d",
    containerClass: "bg-error-bg border-error-border",
    textClass: "text-error",
  },
];

function worstBucketLabel(bucket: string): string {
  const map: Record<string, string> = {
    current: "Corrente",
    "1_30": "1–30 d",
    "31_60": "31–60 d",
    "61_90": "61–90 d",
    over_90: "+90 d",
  };
  return map[bucket] ?? bucket;
}

function bucketBadgeClass(bucket: string): string {
  if (bucket === "over_90" || bucket === "61_90") {
    return "text-error bg-error-bg border border-error-border";
  }
  if (bucket === "31_60") {
    return "text-warning bg-warning-bg border border-warning-border";
  }
  return "text-ink-2 bg-surface-2 border border-border";
}

function bucketDotClass(bucket: string): string {
  if (bucket === "over_90" || bucket === "61_90") return "bg-error";
  if (bucket === "31_60") return "bg-amber";
  return "bg-muted";
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default async function ArPage({
  searchParams,
}: {
  searchParams: Promise<{ as_of?: string }>;
}) {
  await requireSession();

  const sp = await searchParams;
  const asOf = sp.as_of ?? new Date().toISOString().slice(0, 10);
  const asOfParam = `?as_of=${asOf}`;

  let summary: ArSummary | null = null;
  let topDebtors: TopDebtor[] = [];

  try {
    summary = await apiFetch<ArSummary>(`/api/v1/billing/ar/summary${asOfParam}`);
  } catch {
    summary = null;
  }

  try {
    const result = await apiFetch<TopDebtor[]>(
      `/api/v1/billing/ar/top-debtors${asOfParam}&limit=5`
    );
    topDebtors = Array.isArray(result) ? result : [];
  } catch {
    topDebtors = [];
  }

  const totalAr = summary?.total_ar ?? "0";
  const overdueAmount =
    Number(summary?.["31_60"] ?? 0) +
    Number(summary?.["61_90"] ?? 0) +
    Number(summary?.over_90 ?? 0);
  const criticalAmount =
    Number(summary?.["61_90"] ?? 0) + Number(summary?.over_90 ?? 0);

  return (
    <SidebarLayout active="ar">
      <PageHeader
        title="Contas a Receber"
        description={`Referência: ${asOf}`}
      />

      {/* as_of date picker — standard HTML form GET navigation (no client JS needed) */}
      <div className="mb-6 flex items-center gap-3">
        <label
          className="text-sm font-medium text-[var(--muted)]"
          htmlFor="as_of_input"
        >
          Data de referência
        </label>
        <form method="GET" action="/ar" className="flex gap-2">
          <input
            id="as_of_input"
            type="date"
            name="as_of"
            defaultValue={asOf}
            className="px-3 py-1.5 text-sm border border-border rounded-md bg-surface text-ink focus:outline-none focus:ring-2 focus:ring-amber/20 focus:border-amber"
          />
          <button
            type="submit"
            className="px-3 py-1.5 text-sm font-bold rounded-md bg-amber text-ink hover:bg-amber-dark transition-colors duration-100"
          >
            Aplicar
          </button>
        </form>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <KpiCard
          label="Total em Aberto"
          value={`MZN ${formatMzn(totalAr)}`}
          semantic={Number(totalAr) > 0 ? "error" : "default"}
        />
        <KpiCard
          label="Vencido (+30 d)"
          value={`MZN ${formatMzn(String(overdueAmount))}`}
          semantic={criticalAmount > 0 ? "error" : overdueAmount > 0 ? "warning" : "default"}
        />
        <KpiCard
          label="Clientes com Dívida"
          value={String(topDebtors.length)}
          semantic="default"
        />
      </div>

      {/* Aging grid — 5 bucket cards */}
      <SectionHeader title="Aging — Distribuição por Antiguidade" />
      <div className="grid grid-cols-5 gap-3 mb-8">
        {BUCKETS.map(({ key, label, containerClass, textClass }) => {
          const rawVal = summary ? (summary[key] as string | undefined) : undefined;
          const amount = rawVal ?? "0";
          return (
            <div
              key={key}
              className={`rounded-lg border p-4 ${containerClass}`}
            >
              <div
                className={`text-xs font-semibold uppercase tracking-wide mb-2 ${textClass}`}
              >
                {label}
              </div>
              <div className={`font-mono text-lg font-medium tabular-nums ${textClass}`}>
                {formatMzn(amount)}
              </div>
              <div className="text-xs text-[var(--muted)] mt-1">MZN</div>
            </div>
          );
        })}
      </div>

      {/* Top debtors table */}
      <SectionHeader title="Maiores Devedores" />
      {topDebtors.length === 0 ? (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-8 text-sm text-center text-[var(--muted)]">
          Sem clientes com saldo em aberto na data de referência.
        </div>
      ) : (
        <DataTable>
          <TableHeader>
            <TableRow>
              <RotasTableHeader>Cliente</RotasTableHeader>
              <RotasTableHeader className="text-right">
                Saldo em Aberto (MZN)
              </RotasTableHeader>
              <RotasTableHeader className="text-center">
                Pior Bucket
              </RotasTableHeader>
              <RotasTableHeader className="text-center">
                Detalhe
              </RotasTableHeader>
            </TableRow>
          </TableHeader>
          <TableBody>
            {topDebtors.map((debtor) => (
              <RotasTableRow key={debtor.client_id}>
                <RotasTableCell>
                  <span className="font-medium text-[var(--ink)]">
                    {debtor.client_name}
                  </span>
                </RotasTableCell>
                <RotasTableCell className="text-right">
                  <span className="font-mono text-sm font-medium tabular-nums text-[var(--ink)]">
                    {formatMzn(debtor.outstanding)}
                  </span>
                </RotasTableCell>
                <RotasTableCell className="text-center">
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${bucketBadgeClass(debtor.worst_bucket)}`}
                  >
                    <span
                      className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${bucketDotClass(debtor.worst_bucket)}`}
                    />
                    {worstBucketLabel(debtor.worst_bucket)}
                  </span>
                </RotasTableCell>
                <RotasTableCell className="text-center">
                  <Link
                    href={`/clientes/${debtor.client_id}`}
                    className="text-sm text-[var(--blue)] hover:underline"
                  >
                    Ver cliente
                  </Link>
                </RotasTableCell>
              </RotasTableRow>
            ))}
          </TableBody>
        </DataTable>
      )}
    </SidebarLayout>
  );
}
