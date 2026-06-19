import { AlertOctagon, AlertTriangle } from "lucide-react";
import { notFound } from "next/navigation";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { SectionHeader } from "@/app/components/ui/SectionHeader";
import { MonoCell } from "@/app/components/ui/MonoCell";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { EmptyState } from "@/app/components/ui/EmptyState";
import {
  DataTable,
  RotasTableHeader,
  RotasTableRow,
  RotasTableCell,
  TableBody,
  TableHeader,
  TableRow,
} from "@/app/components/ui/DataTable";
import { apiFetch } from "@/app/lib/api";
import type { ClientResponse } from "@/app/lib/clients-api";
import { EditarClienteButton } from "./EditarClienteButton";
import { PaymentModal } from "@/app/components/PaymentModal";

interface Contract {
  id: string;
  contract_reference: string;
  title: string;
  status: string;
  default_unit_price: number | null;
  currency: string;
  starts_at: string | null;
  ends_at: string | null;
  client_id?: string | null;
  client_name?: string | null;
}

interface BillingDocument {
  id: string;
  invoice_number: string | null;
  billing_period_start: string;
  billing_period_end: string;
  total_amount: string | number;
  outstanding_balance?: string | number | null;
  due_date: string | null;
  status: string;
  client_id?: string | null;
}

function formatMzn(val: string | number | null | undefined): string {
  if (val == null) return "—";
  const n = Number(val);
  return `MZN ${n.toLocaleString("pt-MZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDate(d: string | null | undefined): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("pt-MZ", { day: "2-digit", month: "short", year: "numeric" });
}

export default async function ClienteDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let client: ClientResponse;
  try {
    client = await apiFetch<ClientResponse>(`/api/v1/clients/${id}`);
  } catch {
    notFound();
  }

  // Fetch contracts — filter client-side by client_id since query param may not exist
  let contracts: Contract[] = [];
  try {
    const allContracts = await apiFetch<Contract[]>("/api/v1/contracts/?limit=200");
    contracts = Array.isArray(allContracts)
      ? allContracts.filter((c) => c.client_id === id)
      : [];
  } catch {
    contracts = [];
  }

  // Fetch billing documents filtered by client
  let invoices: BillingDocument[] = [];
  try {
    const allDocs = await apiFetch<BillingDocument[]>("/api/v1/billing/documents?limit=200");
    invoices = Array.isArray(allDocs)
      ? allDocs.filter((d) => d.client_id === id)
      : [];
  } catch {
    invoices = [];
  }

  // Credit limit warning computation
  const creditLimit = Number(client.credit_limit ?? 0);
  const outstanding = Number(client.outstanding_balance ?? 0);
  const creditPct = creditLimit > 0 ? (outstanding / creditLimit) * 100 : 0;

  return (
    <SidebarLayout active="clientes">
      <PageHeader
        eyebrow="Cliente"
        title={client.trading_name}
        actions={
          <div className="flex items-center gap-2">
            <PaymentModal
              clientId={id}
              clientName={client.trading_name}
              advanceMode={true}
              trigger={
                <button className="text-xs font-semibold bg-amber-500 hover:bg-amber-600 text-white rounded px-3 py-1.5 transition-colors">
                  Registar Adiantamento
                </button>
              }
            />
            <EditarClienteButton client={client} />
          </div>
        }
      />

      {/* Client info card */}
      <div
        className="grid grid-cols-2 gap-6 p-4 rounded-lg border mb-6"
        style={{ background: "var(--surface)", borderColor: "var(--border)" }}
      >
        {/* Left: identity */}
        <div className="space-y-3">
          <div>
            <span className="block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">NUIT</span>
            <MonoCell size="base">{client.nuit}</MonoCell>
          </div>
          {client.email && (
            <div>
              <span className="block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">Email</span>
              <span className="text-[13px] text-ink">{client.email}</span>
            </div>
          )}
          {client.phone && (
            <div>
              <span className="block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">Telefone</span>
              <span className="text-[13px] text-ink">{client.phone}</span>
            </div>
          )}
          {client.address && (
            <div>
              <span className="block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">Morada</span>
              <span className="text-[13px] text-ink">{client.address}</span>
            </div>
          )}
          {client.city && (
            <div>
              <span className="block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">Cidade</span>
              <span className="text-[13px] text-ink">{client.city}</span>
            </div>
          )}
        </div>

        {/* Right: financial & status */}
        <div className="space-y-3">
          <div>
            <span className="block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">Prazo de pagamento</span>
            <span className="text-[13px] text-ink">{client.payment_terms_days} dias</span>
          </div>
          <div>
            <span className="block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">Limite de crédito</span>
            <MonoCell size="base">
              {creditLimit > 0 ? formatMzn(client.credit_limit) : "Sem limite"}
            </MonoCell>
          </div>
          <div>
            <span className="block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">Saldo em aberto</span>
            <MonoCell
              size="base"
              className={outstanding > 0 ? "text-error" : "text-ink"}
            >
              {formatMzn(client.outstanding_balance)}
            </MonoCell>
          </div>
          <div>
            <span className="block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">Estado</span>
            <StatusBadge status={client.is_active ? "activo" : "inactivo"} />
          </div>
        </div>
      </div>

      {/* Credit limit warning strip */}
      {creditPct >= 80 && (
        <div
          className="flex items-start gap-3 p-4 rounded-lg border mb-6"
          style={{
            background: creditPct >= 100 ? "var(--error-bg)" : "var(--warning-bg)",
            borderColor: creditPct >= 100 ? "var(--error)" : "var(--warning)",
          }}
        >
          {creditPct >= 100 ? (
            <AlertOctagon
              size={18}
              className="flex-shrink-0 mt-0.5"
              style={{ color: "var(--error)" }}
            />
          ) : (
            <AlertTriangle
              size={18}
              className="flex-shrink-0 mt-0.5"
              style={{ color: "var(--warning)" }}
            />
          )}
          <div>
            <p
              className="text-[13px] font-semibold"
              style={{ color: creditPct >= 100 ? "var(--error)" : "var(--warning)" }}
            >
              {creditPct >= 100
                ? `Limite de crédito excedido. Saldo em aberto: ${formatMzn(client.outstanding_balance)} / Limite: ${formatMzn(client.credit_limit)}. Nenhuma acção está bloqueada.`
                : `Saldo em aberto de ${formatMzn(client.outstanding_balance)} está a aproximar-se do limite de crédito (${formatMzn(client.credit_limit)}).`}
            </p>
          </div>
        </div>
      )}

      {/* Contracts panel */}
      <div className="rounded-lg border border-border bg-surface overflow-hidden mb-6">
        <SectionHeader title="Contratos" count={contracts.length} />
        {contracts.length === 0 ? (
          <EmptyState
            title="Sem contratos associados"
            description="Este cliente não tem contratos associados."
          />
        ) : (
          <DataTable>
            <TableHeader>
              <TableRow>
                <RotasTableHeader>Referência</RotasTableHeader>
                <RotasTableHeader>Título</RotasTableHeader>
                <RotasTableHeader>Estado</RotasTableHeader>
                <RotasTableHeader>Preço unit.</RotasTableHeader>
                <RotasTableHeader>Inicia</RotasTableHeader>
                <RotasTableHeader>Termina</RotasTableHeader>
              </TableRow>
            </TableHeader>
            <TableBody>
              {contracts.map((c) => (
                <RotasTableRow key={c.id}>
                  <RotasTableCell>
                    <MonoCell>{c.contract_reference}</MonoCell>
                  </RotasTableCell>
                  <RotasTableCell>{c.title}</RotasTableCell>
                  <RotasTableCell>
                    <StatusBadge status={c.status} />
                  </RotasTableCell>
                  <RotasTableCell>
                    {c.default_unit_price != null ? (
                      <MonoCell>
                        {c.currency} {Number(c.default_unit_price).toLocaleString("pt-MZ", { minimumFractionDigits: 2 })}
                      </MonoCell>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </RotasTableCell>
                  <RotasTableCell>{formatDate(c.starts_at)}</RotasTableCell>
                  <RotasTableCell>{formatDate(c.ends_at)}</RotasTableCell>
                </RotasTableRow>
              ))}
            </TableBody>
          </DataTable>
        )}
      </div>

      {/* Invoices panel */}
      <div className="rounded-lg border border-border bg-surface overflow-hidden">
        <SectionHeader title="Faturas emitidas" count={invoices.length} />
        {invoices.length === 0 ? (
          <EmptyState
            title="Sem faturas emitidas"
            description="Ainda não foram emitidas faturas para este cliente."
          />
        ) : (
          <DataTable>
            <TableHeader>
              <TableRow>
                <RotasTableHeader>Número</RotasTableHeader>
                <RotasTableHeader>Período</RotasTableHeader>
                <RotasTableHeader>Total MZN</RotasTableHeader>
                <RotasTableHeader>Em aberto</RotasTableHeader>
                <RotasTableHeader>Data vcto.</RotasTableHeader>
                <RotasTableHeader>Estado</RotasTableHeader>
                <RotasTableHeader>Acção</RotasTableHeader>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.map((inv) => (
                <RotasTableRow key={inv.id}>
                  <RotasTableCell>
                    <MonoCell className={inv.invoice_number ? "text-ink" : "text-muted"}>
                      {inv.invoice_number ?? "—"}
                    </MonoCell>
                  </RotasTableCell>
                  <RotasTableCell>
                    {formatDate(inv.billing_period_start)} — {formatDate(inv.billing_period_end)}
                  </RotasTableCell>
                  <RotasTableCell>
                    <MonoCell>{formatMzn(inv.total_amount)}</MonoCell>
                  </RotasTableCell>
                  <RotasTableCell>
                    <MonoCell className={Number(inv.outstanding_balance ?? 0) > 0 ? "text-error" : "text-ink"}>
                      {formatMzn(inv.outstanding_balance)}
                    </MonoCell>
                  </RotasTableCell>
                  <RotasTableCell>{formatDate(inv.due_date)}</RotasTableCell>
                  <RotasTableCell>
                    <StatusBadge status={inv.status} />
                  </RotasTableCell>
                  <RotasTableCell>
                    {(inv.status === "issued" || inv.status === "overdue") && (
                      <PaymentModal
                        clientId={id}
                        clientName={client.trading_name}
                        invoiceId={inv.id}
                        invoiceNumber={inv.invoice_number}
                        invoiceTotal={inv.total_amount != null ? String(inv.total_amount) : null}
                        invoiceOutstanding={inv.outstanding_balance != null ? String(inv.outstanding_balance) : null}
                        trigger={
                          <button className="text-xs font-semibold text-amber-600 hover:text-amber-700 border border-amber-200 rounded px-2 py-1">
                            Registar Pagamento
                          </button>
                        }
                      />
                    )}
                  </RotasTableCell>
                </RotasTableRow>
              ))}
            </TableBody>
          </DataTable>
        )}
      </div>
    </SidebarLayout>
  );
}
