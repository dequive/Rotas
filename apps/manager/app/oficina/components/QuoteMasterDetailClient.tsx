"use client";

import {
  CheckCircle2,
  FileLock2,
  RefreshCw,
  Search,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/app/components/ui/Button";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { bffRequest } from "@/app/lib/bff";
import type { WorkshopQuote } from "@/app/lib/workshop-api";

import { AcceptQuoteModal } from "./AcceptQuoteModal";
import { QuoteFormModal } from "./QuoteFormModal";

interface VehicleOption {
  id: string;
  plate: string;
  brand?: string;
  model?: string;
}

interface ReceptionContext {
  id: string;
  vehicleId: string;
  clientId: string | null;
  number: string;
}

interface QuoteMasterDetailClientProps {
  initialQuotes: WorkshopQuote[];
  vehicleOptions: VehicleOption[];
  initialReception?: ReceptionContext | null;
}

const money = new Intl.NumberFormat("pt-MZ", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

async function readApiError(response: Response, fallback: string) {
  const body = (await response.json().catch(() => ({}))) as {
    detail?: string;
    error?: { message?: string };
  };
  return body.error?.message ?? body.detail ?? fallback;
}

export function QuoteMasterDetailClient({
  initialQuotes,
  vehicleOptions,
  initialReception,
}: QuoteMasterDetailClientProps) {
  const [quotes, setQuotes] = useState(initialQuotes);
  const [selectedId, setSelectedId] = useState(initialQuotes[0]?.id ?? null);
  const [detail, setDetail] = useState<WorkshopQuote | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [acceptOpen, setAcceptOpen] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const vehicleById = useMemo(
    () => new Map(vehicleOptions.map((vehicle) => [vehicle.id, vehicle])),
    [vehicleOptions],
  );

  const loadDetail = useCallback(async (quoteId: string) => {
    setLoadingDetail(true);
    setError(null);
    try {
      const response = await bffRequest(`/api/v1/workshop/quotes/${quoteId}`);
      if (!response.ok) {
        throw new Error(
          await readApiError(response, "Não foi possível carregar o orçamento."),
        );
      }
      setDetail((await response.json()) as WorkshopQuote);
    } catch (err) {
      setDetail(null);
      setError(
        err instanceof Error ? err.message : "Erro ao carregar o orçamento.",
      );
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId);
    else setDetail(null);
  }, [loadDetail, selectedId]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const response = await bffRequest("/api/v1/workshop/quotes?limit=200");
      if (!response.ok) {
        throw new Error(
          await readApiError(response, "Não foi possível atualizar os orçamentos."),
        );
      }
      const nextQuotes = (await response.json()) as WorkshopQuote[];
      setQuotes(nextQuotes);
      const nextSelected =
        selectedId && nextQuotes.some((quote) => quote.id === selectedId)
          ? selectedId
          : nextQuotes[0]?.id ?? null;
      setSelectedId(nextSelected);
      if (nextSelected) await loadDetail(nextSelected);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erro ao atualizar os orçamentos.",
      );
    } finally {
      setRefreshing(false);
    }
  }, [loadDetail, selectedId]);

  const filteredQuotes = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return quotes.filter((quote) => {
      const vehicle = vehicleById.get(quote.vehicle_id);
      const matchesSearch =
        !normalizedSearch ||
        quote.quote_number.toLowerCase().includes(normalizedSearch) ||
        vehicle?.plate.toLowerCase().includes(normalizedSearch) ||
        quote.client_id?.toLowerCase().includes(normalizedSearch);
      return matchesSearch && (!status || quote.status === status);
    });
  }, [quotes, search, status, vehicleById]);

  async function acceptQuote(data: {
    acceptance_channel: string;
    accepted_by_person_name: string;
  }) {
    if (!detail) return;
    const response = await bffRequest(
      `/api/v1/workshop/quotes/${detail.id}/accept`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify(data),
      },
    );
    if (!response.ok) {
      throw new Error(
        await readApiError(response, "Não foi possível aceitar o orçamento."),
      );
    }
    await refresh();
  }

  async function rejectQuote() {
    if (!detail || !rejectReason.trim()) return;
    setRejecting(true);
    setError(null);
    try {
      const response = await bffRequest(
        `/api/v1/workshop/quotes/${detail.id}/reject`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({ reason: rejectReason.trim() }),
        },
      );
      if (!response.ok) {
        throw new Error(
          await readApiError(response, "Não foi possível rejeitar o orçamento."),
        );
      }
      setRejectReason("");
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erro ao rejeitar o orçamento.",
      );
    } finally {
      setRejecting(false);
    }
  }

  const selectedVehicle = detail ? vehicleById.get(detail.vehicle_id) : null;
  const isImmutable = detail ? detail.status !== "sent" : false;

  return (
    <div className="space-y-4">
      {initialReception && (
        <div className="flex flex-col gap-3 rounded-[var(--r-md)] border border-status-reception bg-status-reception-soft p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-status-reception">
              Orçamento vinculado à receção {initialReception.number}
            </p>
            <p className="mt-1 text-xs text-muted">
              A viatura e o cliente serão herdados da ficha de entrada.
            </p>
          </div>
          <QuoteFormModal
            vehicleOptions={vehicleOptions}
            initialVehicleId={initialReception.vehicleId}
            initialClientId={initialReception.clientId}
            initialReceptionId={initialReception.id}
            triggerLabel="Criar para esta receção"
            triggerVariant="primary"
            onSuccess={refresh}
          />
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-[var(--r-md)] border border-status-cancelled bg-status-cancelled-soft p-3 text-sm text-status-cancelled"
        >
          {error}
        </div>
      )}

      <div className="grid min-h-[620px] grid-cols-1 overflow-hidden rounded-[var(--r-lg)] border border-border bg-surface shadow-card lg:grid-cols-[360px_minmax(0,1fr)]">
        <section className="border-b border-border lg:border-b-0 lg:border-r">
          <div className="space-y-3 border-b border-border p-4">
            <div className="relative">
              <Search
                aria-hidden="true"
                className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
              />
              <label htmlFor="quote-search" className="sr-only">
                Pesquisar orçamentos
              </label>
              <input
                id="quote-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Número, matrícula ou cliente"
                className="h-10 w-full rounded-[var(--r-md)] border border-border-strong bg-surface pl-9 pr-3 text-sm text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
              />
            </div>
            <div className="flex gap-2">
              <label htmlFor="quote-status" className="sr-only">
                Filtrar por estado
              </label>
              <select
                id="quote-status"
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="h-10 min-w-0 flex-1 rounded-[var(--r-md)] border border-border-strong bg-surface px-3 text-sm text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
              >
                <option value="">Todos os estados</option>
                <option value="sent">Aguardando aprovação</option>
                <option value="converted">Convertido em OS</option>
                <option value="rejected">Rejeitado</option>
                <option value="expired">Vencido</option>
              </select>
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-label="Atualizar orçamentos"
                loading={refreshing}
                onClick={refresh}
              >
                {!refreshing && <RefreshCw aria-hidden="true" className="h-4 w-4" />}
              </Button>
            </div>
          </div>

          <div className="max-h-[520px] overflow-y-auto lg:max-h-[720px]">
            {filteredQuotes.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-sm font-medium text-ink">
                  Nenhum orçamento encontrado
                </p>
                <p className="mt-1 text-xs text-muted">
                  Ajuste os filtros ou crie um novo orçamento.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {filteredQuotes.map((quote) => {
                  const vehicle = vehicleById.get(quote.vehicle_id);
                  const selected = selectedId === quote.id;
                  return (
                    <li key={quote.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(quote.id)}
                        className={`w-full border-l-4 p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus ${
                          selected
                            ? "border-l-rotas-500 bg-rotas-50 dark:bg-surface-2"
                            : "border-l-transparent hover:bg-surface-2"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-mono text-sm font-semibold tabular-nums text-ink">
                              {quote.quote_number}
                            </p>
                            <p className="mt-1 text-xs text-muted">
                              {vehicle?.plate ?? quote.vehicle_id}
                            </p>
                          </div>
                          <StatusBadge status={quote.status} />
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-3">
                          <span className="text-xs font-medium text-muted">
                            {quote.is_supplemental ? "Suplementar" : "Inicial"}
                          </span>
                          <span className="font-mono text-sm font-semibold tabular-nums text-ink">
                            {money.format(Number(quote.total_amount) || 0)} MT
                          </span>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        <section className="min-w-0 p-4 sm:p-6">
          {loadingDetail ? (
            <div className="space-y-4 animate-pulse" aria-label="A carregar detalhe">
              <div className="h-7 w-48 rounded bg-border" />
              <div className="h-28 rounded bg-surface-2" />
              <div className="h-52 rounded bg-surface-2" />
            </div>
          ) : !detail ? (
            <div className="flex min-h-[360px] items-center justify-center text-center">
              <div>
                <FileLock2 aria-hidden="true" className="mx-auto h-8 w-8 text-muted" />
                <p className="mt-3 text-sm font-medium text-ink">
                  Selecione um orçamento
                </p>
                <p className="mt-1 text-xs text-muted">
                  O documento e as ações comerciais surgirão neste painel.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-mono text-xl font-semibold tabular-nums text-ink">
                      {detail.quote_number}
                    </h2>
                    <StatusBadge status={detail.status} />
                    {detail.is_supplemental && (
                      <StatusBadge
                        status="supplemental"
                        label="Suplementar"
                      />
                    )}
                  </div>
                  <p className="mt-2 text-sm text-muted">
                    {selectedVehicle
                      ? `${selectedVehicle.plate} · ${selectedVehicle.brand ?? ""} ${selectedVehicle.model ?? ""}`.trim()
                      : detail.vehicle_id}
                  </p>
                </div>
                {detail.status === "sent" && (
                  <Button
                    type="button"
                    variant="primary"
                    onClick={() => setAcceptOpen(true)}
                  >
                    <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
                    Aprovar e gerar OS
                  </Button>
                )}
                {detail.status === "converted" &&
                  detail.related_work_order_id && (
                    <QuoteFormModal
                      vehicleOptions={vehicleOptions}
                      initialVehicleId={detail.vehicle_id}
                      initialClientId={detail.client_id}
                      initialReceptionId={detail.reception_id}
                      isSupplemental
                      relatedWorkOrderId={detail.related_work_order_id}
                      triggerVariant="primary"
                      onSuccess={refresh}
                    />
                  )}
              </div>

              {isImmutable && (
                <div className="flex gap-3 rounded-[var(--r-md)] border border-border bg-surface-2 p-4">
                  <FileLock2
                    aria-hidden="true"
                    className="mt-0.5 h-5 w-5 flex-none text-muted"
                  />
                  <div>
                    <p className="text-sm font-semibold text-ink">
                      Documento imutável
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-muted">
                      Este orçamento já saiu do estado de aprovação. Correções
                      não alteram o original; trabalho adicional exige um
                      suplemento separado e nova aceitação.
                    </p>
                  </div>
                </div>
              )}

              <dl className="grid grid-cols-2 gap-4 rounded-[var(--r-md)] border border-border bg-surface-2 p-4 sm:grid-cols-4">
                <div>
                  <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                    Criado
                  </dt>
                  <dd className="mt-1 text-sm font-medium text-ink">
                    {new Date(detail.created_at).toLocaleDateString("pt-MZ")}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                    Validade
                  </dt>
                  <dd className="mt-1 text-sm font-medium text-ink">
                    {detail.valid_until
                      ? new Date(detail.valid_until).toLocaleDateString("pt-MZ")
                      : "Sem prazo"}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                    Canal
                  </dt>
                  <dd className="mt-1 text-sm font-medium text-ink">
                    {detail.acceptance_channel || "Não registado"}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                    Autorizado por
                  </dt>
                  <dd className="mt-1 text-sm font-medium text-ink">
                    {detail.accepted_by_person_name || "Não registado"}
                  </dd>
                </div>
              </dl>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-ink">
                  Itens do orçamento
                </h3>
                <div className="overflow-x-auto rounded-[var(--r-md)] border border-border">
                  <table className="w-full min-w-[640px] text-left text-sm">
                    <thead className="bg-surface-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
                      <tr>
                        <th className="px-3 py-2.5">Tipo</th>
                        <th className="px-3 py-2.5">Descrição</th>
                        <th className="px-3 py-2.5 text-right">Qtd.</th>
                        <th className="px-3 py-2.5 text-right">Unitário</th>
                        <th className="px-3 py-2.5 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {detail.items?.length ? (
                        detail.items.map((item) => (
                          <tr key={item.id}>
                            <td className="px-3 py-3 text-muted">
                              {item.item_type === "labor" ? "Mão de obra" : "Peça"}
                            </td>
                            <td className="px-3 py-3 font-medium text-ink">
                              {item.description}
                            </td>
                            <td className="px-3 py-3 text-right font-mono tabular-nums text-ink">
                              {item.quantity}
                            </td>
                            <td className="px-3 py-3 text-right font-mono tabular-nums text-ink">
                              {money.format(Number(item.unit_price) || 0)} MT
                            </td>
                            <td className="px-3 py-3 text-right font-mono font-semibold tabular-nums text-ink">
                              {money.format(
                                (Number(item.quantity) || 0) *
                                  (Number(item.unit_price) || 0),
                              )}{" "}
                              MT
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td
                            colSpan={5}
                            className="px-3 py-8 text-center text-sm text-muted"
                          >
                            Nenhum item registado.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="ml-auto max-w-sm space-y-2 rounded-[var(--r-md)] border border-border bg-surface-2 p-4 font-mono text-sm tabular-nums">
                <div className="flex justify-between gap-4 text-muted">
                  <span>Mão de obra</span>
                  <span>{money.format(Number(detail.labor_total) || 0)} MT</span>
                </div>
                <div className="flex justify-between gap-4 text-muted">
                  <span>Peças</span>
                  <span>{money.format(Number(detail.parts_total) || 0)} MT</span>
                </div>
                <div className="flex justify-between gap-4 text-muted">
                  <span>IVA</span>
                  <span>{money.format(Number(detail.tax_total) || 0)} MT</span>
                </div>
                <div className="flex justify-between gap-4 border-t border-border pt-2 text-base font-bold text-ink">
                  <span>Total</span>
                  <span>{money.format(Number(detail.total_amount) || 0)} MT</span>
                </div>
              </div>

              {detail.notes && (
                <div>
                  <h3 className="text-sm font-semibold text-ink">Observações</h3>
                  <p className="mt-2 whitespace-pre-wrap rounded-[var(--r-md)] border border-border bg-surface-2 p-4 text-sm leading-relaxed text-muted">
                    {detail.notes}
                  </p>
                </div>
              )}

              {detail.status === "sent" && (
                <div className="space-y-3 border-t border-border pt-5">
                  <label
                    htmlFor="reject-reason"
                    className="text-sm font-semibold text-ink"
                  >
                    Recusar orçamento
                  </label>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <input
                      id="reject-reason"
                      value={rejectReason}
                      onChange={(event) => setRejectReason(event.target.value)}
                      placeholder="Motivo obrigatório para a trilha de auditoria"
                      className="h-10 min-w-0 flex-1 rounded-[var(--r-md)] border border-border-strong bg-surface px-3 text-sm text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
                    />
                    <Button
                      type="button"
                      variant="destructive"
                      disabled={!rejectReason.trim()}
                      loading={rejecting}
                      onClick={rejectQuote}
                    >
                      {!rejecting && (
                        <XCircle aria-hidden="true" className="h-4 w-4" />
                      )}
                      Recusar
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      {detail && (
        <AcceptQuoteModal
          open={acceptOpen}
          onClose={() => setAcceptOpen(false)}
          quoteNumber={detail.quote_number}
          totalAmount={Number(detail.total_amount) || 0}
          onAccept={acceptQuote}
        />
      )}
    </div>
  );
}
