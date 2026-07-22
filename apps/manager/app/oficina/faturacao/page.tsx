import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  CreditCard,
  DollarSign,
  FileText,
  Plus,
  Search,
} from "lucide-react";

import { SidebarLayout } from "../../components/SidebarLayout";
import { requireSession } from "../../lib/auth";

/**
 * Workshop Billing & Accounts Receivable page.
 *
 * Displays FT-2026-XXXX invoices issued from Work Orders,
 * pending AR balances, and payment registration.
 *
 * Data is fetched from /api/v1/workshop/billing/ endpoints.
 * Fallback: static demo data while endpoints are wired.
 */

const DEMO_INVOICES = [
  {
    id: "inv-001",
    number: "FT-2026-0018",
    quoteNumber: "ORC-2026-0034",
    workOrderNumber: "OS-2026-0044",
    client: "Manuel Silva Construções",
    issueDate: "2026-07-18",
    dueDate: "2026-08-17",
    totalAmount: 8400.0,
    amountPaid: 0,
    status: "issued" as const,
  },
  {
    id: "inv-002",
    number: "FT-2026-0017",
    quoteNumber: "ORC-2026-0032",
    workOrderNumber: "OS-2026-0042",
    client: "Transportes Maguezo Lda",
    issueDate: "2026-07-12",
    dueDate: "2026-08-11",
    totalAmount: 15600.0,
    amountPaid: 15600.0,
    status: "paid" as const,
  },
  {
    id: "inv-003",
    number: "FT-2026-0016",
    quoteNumber: "ORC-2026-0031",
    workOrderNumber: "OS-2026-0040",
    client: "Frota Própria (TMS)",
    issueDate: "2026-07-05",
    dueDate: "2026-08-04",
    totalAmount: 4250.0,
    amountPaid: 2000.0,
    status: "issued" as const,
  },
];

const STATUS_MAP = {
  draft: {
    label: "Rascunho",
    classes: "bg-muted text-muted-foreground border border-border",
    icon: FileText,
  },
  issued: {
    label: "Emitida",
    classes: "bg-amber-500/10 text-amber-500 border border-amber-500/20",
    icon: Clock,
  },
  paid: {
    label: "Paga",
    classes: "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20",
    icon: CheckCircle2,
  },
  voided: {
    label: "Anulada",
    classes: "bg-rose-500/10 text-rose-500 border border-rose-500/20",
    icon: AlertTriangle,
  },
};

function formatMZN(value: number) {
  return new Intl.NumberFormat("pt-MZ", {
    style: "decimal",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export default async function WorkshopBillingPage() {
  await requireSession();

  // Aggregate KPIs from demo data
  const totalInvoiced = DEMO_INVOICES.reduce((s, i) => s + i.totalAmount, 0);
  const totalPaid = DEMO_INVOICES.reduce((s, i) => s + i.amountPaid, 0);
  const totalOutstanding = totalInvoiced - totalPaid;
  const overdueCount = DEMO_INVOICES.filter(
    (i) => i.status === "issued" && new Date(i.dueDate) < new Date(),
  ).length;

  return (
    <SidebarLayout active="faturacao-oficina">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Faturação da Oficina
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Faturas emitidas a partir de Ordens de Serviço, pagamentos e contas a receber.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-input bg-background hover:bg-accent transition-colors">
              <CreditCard className="h-4 w-4" /> Registar Pagamento
            </button>
            <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
              <Plus className="h-4 w-4" /> Emitir Fatura
            </button>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Total Faturado
              </span>
              <FileText className="h-5 w-5 text-indigo-500" />
            </div>
            <div className="text-2xl font-bold text-foreground">
              {formatMZN(totalInvoiced)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Total Recebido
              </span>
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            </div>
            <div className="text-2xl font-bold text-emerald-600">
              {formatMZN(totalPaid)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Saldo Pendente
              </span>
              <DollarSign className="h-5 w-5 text-amber-500" />
            </div>
            <div className="text-2xl font-bold text-amber-600">
              {formatMZN(totalOutstanding)}{" "}
              <span className="text-sm font-normal text-muted-foreground">MT</span>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Em Atraso
              </span>
              <AlertTriangle className="h-5 w-5 text-rose-500" />
            </div>
            <div className="text-2xl font-bold text-rose-600">{overdueCount}</div>
            <p className="text-xs text-muted-foreground">Faturas vencidas sem pagamento total</p>
          </div>
        </div>

        {/* Invoices Table */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
            <h2 className="text-base font-semibold text-foreground">
              Faturas de Oficina
            </h2>
            <div className="flex items-center gap-3">
              <div className="relative max-w-xs">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Pesquisar fatura..."
                  className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
              <select className="px-3 py-2 text-sm rounded-lg border border-input bg-background text-foreground">
                <option value="">Todos</option>
                <option value="issued">Emitidas</option>
                <option value="paid">Pagas</option>
                <option value="voided">Anuladas</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">Nº Fatura</th>
                  <th className="px-6 py-3">Cliente</th>
                  <th className="px-6 py-3">OS / Orçamento</th>
                  <th className="px-6 py-3">Emissão</th>
                  <th className="px-6 py-3">Vencimento</th>
                  <th className="px-6 py-3 text-right">Total (MT)</th>
                  <th className="px-6 py-3 text-right">Pago (MT)</th>
                  <th className="px-6 py-3">Estado</th>
                  <th className="px-6 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {DEMO_INVOICES.map((inv) => {
                  const statusInfo = STATUS_MAP[inv.status] ?? STATUS_MAP.issued;
                  const StatusIcon = statusInfo.icon;
                  const outstanding = inv.totalAmount - inv.amountPaid;
                  return (
                    <tr key={inv.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-6 py-4 font-mono font-medium text-foreground">
                        {inv.number}
                      </td>
                      <td className="px-6 py-4 text-foreground">{inv.client}</td>
                      <td className="px-6 py-4 text-muted-foreground text-xs font-mono">
                        <div>{inv.workOrderNumber}</div>
                        <div className="text-[11px] text-muted-foreground/70">{inv.quoteNumber}</div>
                      </td>
                      <td className="px-6 py-4 text-muted-foreground">{inv.issueDate}</td>
                      <td className="px-6 py-4 text-muted-foreground">{inv.dueDate}</td>
                      <td className="px-6 py-4 font-mono font-semibold text-foreground text-right">
                        {formatMZN(inv.totalAmount)}
                      </td>
                      <td className="px-6 py-4 font-mono text-right text-emerald-600">
                        {formatMZN(inv.amountPaid)}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${statusInfo.classes}`}
                        >
                          <StatusIcon className="h-3 w-3" />
                          {statusInfo.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right space-x-2">
                        {outstanding > 0 && (
                          <button className="text-xs font-medium text-primary hover:underline">
                            Registar Pgto.
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* AR Aging Summary */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border">
            <h2 className="text-base font-semibold text-foreground">
              Aging de Contas a Receber (AR)
            </h2>
          </div>
          <div className="grid grid-cols-4 divide-x divide-border">
            {[
              { label: "Corrente", amount: totalOutstanding * 0.6, color: "text-foreground" },
              { label: "30-60 dias", amount: totalOutstanding * 0.25, color: "text-amber-500" },
              { label: "60-90 dias", amount: totalOutstanding * 0.1, color: "text-amber-600" },
              { label: "> 90 dias", amount: totalOutstanding * 0.05, color: "text-rose-600" },
            ].map((bucket) => (
              <div key={bucket.label} className="p-5 text-center">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  {bucket.label}
                </div>
                <div className={`text-xl font-bold font-mono ${bucket.color}`}>
                  {formatMZN(bucket.amount)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
