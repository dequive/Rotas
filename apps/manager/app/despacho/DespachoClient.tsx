"use client";

import { useState } from "react";
import {
  AlertTriangle,
  BadgeCheck,
  Check,
  Clock,
  Download,
  FileText,
  Loader2,
  Plus,
  X,
} from "lucide-react";
import { MonoCell } from "@/app/components/ui/MonoCell";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { bffRequest } from "@/app/lib/bff";

type Trip = {
  id: string;
  origin: string;
  destination: string;
  status: string;
  actual_departure: string | null;
  actual_arrival: string | null;
  driver_id: string | null;
  vehicle_id: string | null;
};

type Settlement = {
  id: string;
  trip_id: string;
  advance_amount_mzn: string;
  total_costs_mzn: string;
  balance_mzn: string;
  status: "pending" | "approved" | "rejected";
  rejection_reason: string | null;
  pdf_file_id: string | null;
};

type Advance = {
  id: string;
  amount_mzn: string;
  status: string;
  notes: string | null;
};

function money(value: string | number | null) {
  if (value === null || value === undefined) return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  return new Intl.NumberFormat("pt-MZ", {
    style: "currency",
    currency: "MZN",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-MZ", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function shortId(id: string) {
  return id.slice(0, 8).toUpperCase();
}

// ── Settlement status badge ───────────────────────────────────────────────────

function SettlementStatusBadge({ status }: { status: Settlement["status"] | null }) {
  if (!status) return <StatusBadge status="draft" label="Sem despacho" />;
  const map: Record<string, { label: string; status: string }> = {
    pending: { label: "Pendente", status: "pending" },
    approved: { label: "Aprovado", status: "approved" },
    rejected: { label: "Rejeitado", status: "blocked" },
  };
  const m = map[status] ?? { label: status, status: "draft" };
  return <StatusBadge status={m.status} label={m.label} />;
}

// ── Issue Advance Modal ───────────────────────────────────────────────────────

function IssueAdvanceModal({
  trip,
  onClose,
  onDone,
}: {
  trip: Trip;
  onClose: () => void;
  onDone: () => void;
}) {
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const amountNum = parseFloat(amount);
    if (!amount || isNaN(amountNum) || amountNum <= 0) {
      setError("Introduza um valor positivo.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const key = crypto.randomUUID();
      const res = await bffRequest(`/api/v1/trips/${trip.id}/advance`, {
        method: "POST",
        headers: { "Idempotency-Key": key },
        body: JSON.stringify({
          driver_id: trip.driver_id,
          amount_mzn: amountNum,
          notes: notes || null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? body?.detail ?? `HTTP ${res.status}`);
      }
      onDone();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro desconhecido.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-[420px] rounded-xl border border-border bg-surface shadow-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[15px] font-semibold text-ink">Emitir Adiantamento</h2>
          <button
            onClick={onClose}
            className="h-7 w-7 flex items-center justify-center rounded-md border-0 bg-transparent cursor-pointer text-muted"
          >
            <X size={14} />
          </button>
        </div>

        <p className="text-[12px] mb-4 text-muted">
          Viagem:{" "}
          <span className="font-mono font-medium">{shortId(trip.id)}</span> —{" "}
          {trip.origin} → {trip.destination}
        </p>

        <div className="flex flex-col gap-3">
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wide mb-1 text-muted">
              Valor (MZN)
            </label>
            <input
              type="number"
              min="1"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="w-full h-9 px-3 rounded-md border border-border bg-surface-2 text-[13px] font-mono text-ink outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wide mb-1 text-muted">
              Notas (opcional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-md border border-border bg-surface-2 text-[13px] text-ink outline-none resize-none focus:border-amber focus:ring-1 focus:ring-amber/20"
            />
          </div>
        </div>

        {error && (
          <p className="mt-3 text-[12px] text-error flex items-center gap-1">
            <AlertTriangle size={12} /> {error}
          </p>
        )}

        <div className="flex items-center justify-end gap-2 mt-5">
          <button
            onClick={onClose}
            className="h-8 px-3 text-[13px] rounded-md border border-border bg-transparent text-muted cursor-pointer"
          >
            Cancelar
          </button>
          <button
            onClick={submit}
            disabled={loading}
            className="h-8 px-4 text-[13px] font-semibold rounded-md border-0 bg-amber text-black cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
          >
            {loading ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            Emitir
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Reject Settlement Modal ───────────────────────────────────────────────────

function RejectModal({
  tripId,
  onClose,
  onDone,
}: {
  tripId: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!reason.trim()) {
      setError("Introduza o motivo da rejeição.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await bffRequest(`/api/v1/trips/${tripId}/settlement/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? body?.detail ?? `HTTP ${res.status}`);
      }
      onDone();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro desconhecido.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-[400px] rounded-xl border border-border bg-surface shadow-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[15px] font-semibold text-ink">Rejeitar Liquidação</h2>
          <button onClick={onClose} className="h-7 w-7 flex items-center justify-center rounded-md border-0 bg-transparent cursor-pointer text-muted">
            <X size={14} />
          </button>
        </div>
        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wide mb-1 text-muted">
            Motivo
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 rounded-md border border-border bg-surface-2 text-[13px] text-ink outline-none resize-none focus:border-amber focus:ring-1 focus:ring-amber/20"
          />
        </div>
        {error && (
          <p className="mt-2 text-[12px] text-error flex items-center gap-1">
            <AlertTriangle size={12} /> {error}
          </p>
        )}
        <div className="flex items-center justify-end gap-2 mt-4">
          <button onClick={onClose} className="h-8 px-3 text-[13px] rounded-md border border-border bg-transparent text-muted cursor-pointer">
            Cancelar
          </button>
          <button
            onClick={submit}
            disabled={loading}
            className="h-8 px-4 text-[13px] font-semibold rounded-md border-0 bg-error text-white cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
          >
            {loading ? <Loader2 size={13} className="animate-spin" /> : <X size={13} />}
            Rejeitar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Active Trips Table (issue advance) ───────────────────────────────────────

function ActiveTripsTable({ trips }: { trips: Trip[] }) {
  const [issuing, setIssuing] = useState<Trip | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  void refreshKey;

  if (trips.length === 0) {
    return (
      <p className="px-4 py-6 text-[13px] text-muted">
        Sem viagens activas.
      </p>
    );
  }

  return (
    <>
      {issuing && (
        <IssueAdvanceModal
          trip={issuing}
          onClose={() => setIssuing(null)}
          onDone={() => setRefreshKey((k) => k + 1)}
        />
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead className="border-b border-border bg-surface-2">
            <tr>
              <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">ID</th>
              <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Rota</th>
              <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Estado</th>
              <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Partida</th>
              <th className="px-3 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {trips.map((trip) => (
              <tr key={trip.id} className="border-b border-border">
                <td className="px-3 py-2.5">
                  <MonoCell>{shortId(trip.id)}</MonoCell>
                </td>
                <td className="px-3 py-2.5 text-ink">
                  {trip.origin} → {trip.destination}
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge
                    status={trip.status === "planned" ? "planeada" : "em_viagem"}
                    label={trip.status === "planned" ? "Planeada" : "Em curso"}
                  />
                </td>
                <td className="px-3 py-2.5 text-muted">
                  {fmtDate(trip.actual_departure ?? trip.actual_departure)}
                </td>
                <td className="px-3 py-2.5 text-right">
                  <button
                    onClick={() => setIssuing(trip)}
                    className="inline-flex items-center gap-1.5 h-7 px-3 text-[12px] font-semibold rounded-md border-0 bg-amber text-black cursor-pointer"
                  >
                    <Plus size={12} />
                    Emitir Adiantamento
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ── Completed Trips Table (settlement) ───────────────────────────────────────

type SettlementRow = {
  trip: Trip;
  settlement: Settlement | null;
  advance: Advance | null;
};

function CompletedTripsTable({ rows, onRefresh }: { rows: SettlementRow[]; onRefresh: () => void }) {
  const [computing, setComputing] = useState<string | null>(null);
  const [approving, setApproving] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<Record<string, string>>({});

  async function computeSettlement(tripId: string) {
    setComputing(tripId);
    setActionError((e) => ({ ...e, [tripId]: "" }));
    try {
      const res = await bffRequest(`/api/v1/trips/${tripId}/settlement`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? body?.detail ?? `HTTP ${res.status}`);
      }
      onRefresh();
    } catch (e) {
      setActionError((err) => ({
        ...err,
        [tripId]: e instanceof Error ? e.message : "Erro",
      }));
    } finally {
      setComputing(null);
    }
  }

  async function approveSettlement(tripId: string) {
    setApproving(tripId);
    try {
      const res = await bffRequest(`/api/v1/trips/${tripId}/settlement/approve`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? body?.detail ?? `HTTP ${res.status}`);
      }
      onRefresh();
    } catch (e) {
      setActionError((err) => ({
        ...err,
        [tripId]: e instanceof Error ? e.message : "Erro",
      }));
    } finally {
      setApproving(null);
    }
  }

  async function downloadPdf(tripId: string) {
    setDownloading(tripId);
    try {
      const res = await bffRequest(`/api/v1/trips/${tripId}/settlement/pdf`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `despacho-${tripId.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setActionError((err) => ({
        ...err,
        [tripId]: e instanceof Error ? e.message : "Erro ao descarregar PDF",
      }));
    } finally {
      setDownloading(null);
    }
  }

  if (rows.length === 0) {
    return (
      <p className="px-4 py-6 text-[13px] text-muted">
        Sem viagens concluídas.
      </p>
    );
  }

  return (
    <>
      {rejecting && (
        <RejectModal
          tripId={rejecting}
          onClose={() => setRejecting(null)}
          onDone={onRefresh}
        />
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead className="border-b border-border bg-surface-2">
            <tr>
              <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">ID</th>
              <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Rota</th>
              <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Chegada</th>
              <th className="text-right px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Adiantamento</th>
              <th className="text-right px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Despesas</th>
              <th className="text-right px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Saldo</th>
              <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Estado</th>
              <th className="px-3 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ trip, settlement, advance }) => {
              const balanceNum = settlement ? parseFloat(settlement.balance_mzn) : null;
              const isComputing = computing === trip.id;
              const isApproving = approving === trip.id;
              const isDownloading = downloading === trip.id;
              const err = actionError[trip.id];

              return (
                <tr key={trip.id} className="border-b border-border">
                  <td className="px-3 py-2.5">
                    <MonoCell>{shortId(trip.id)}</MonoCell>
                  </td>
                  <td className="px-3 py-2.5 text-ink">
                    {trip.origin} → {trip.destination}
                  </td>
                  <td className="px-3 py-2.5 text-muted">
                    {fmtDate(trip.actual_arrival)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-muted">
                    {settlement ? money(settlement.advance_amount_mzn) : advance ? money(advance.amount_mzn) : "—"}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-ink">
                    {settlement ? money(settlement.total_costs_mzn) : "—"}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono font-semibold">
                    {balanceNum !== null ? (
                      <span className={balanceNum >= 0 ? "text-amber" : "text-error"}>
                        {money(Math.abs(balanceNum))}
                        <span className="text-[10px] ml-1 font-normal">
                          {balanceNum >= 0 ? "↑ emp." : "↑ mot."}
                        </span>
                      </span>
                    ) : "—"}
                  </td>
                  <td className="px-3 py-2.5">
                    <SettlementStatusBadge status={settlement?.status ?? null} />
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center justify-end gap-1.5">
                      {!settlement && (
                        <button
                          onClick={() => computeSettlement(trip.id)}
                          disabled={isComputing}
                          className="inline-flex items-center gap-1 h-7 px-2.5 text-[11px] font-semibold rounded-md border border-border bg-surface-2 text-ink cursor-pointer disabled:opacity-50"
                          title="Calcular liquidação"
                        >
                          {isComputing ? <Loader2 size={11} className="animate-spin" /> : <FileText size={11} />}
                          Calcular
                        </button>
                      )}

                      {settlement?.status === "pending" && (
                        <>
                          <button
                            onClick={() => approveSettlement(trip.id)}
                            disabled={isApproving}
                            className="inline-flex items-center gap-1 h-7 px-2.5 text-[11px] font-semibold rounded-md border-0 bg-success text-white cursor-pointer disabled:opacity-50"
                            title="Aprovar liquidação"
                          >
                            {isApproving ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                          </button>
                          <button
                            onClick={() => setRejecting(trip.id)}
                            className="inline-flex items-center gap-1 h-7 px-2.5 text-[11px] font-semibold rounded-md border-0 bg-error text-white cursor-pointer"
                            title="Rejeitar liquidação"
                          >
                            <X size={11} />
                          </button>
                        </>
                      )}

                      {settlement?.status === "approved" && (
                        <BadgeCheck size={15} className="text-success" />
                      )}

                      {settlement && (
                        <button
                          onClick={() => downloadPdf(trip.id)}
                          disabled={isDownloading}
                          className="inline-flex items-center gap-1 h-7 px-2.5 text-[11px] font-semibold rounded-md border border-border bg-surface-2 text-ink cursor-pointer disabled:opacity-50"
                          title="Descarregar PDF"
                        >
                          {isDownloading ? <Loader2 size={11} className="animate-spin" /> : <Download size={11} />}
                        </button>
                      )}
                    </div>

                    {err && (
                      <p className="text-[11px] text-error mt-0.5 flex items-center gap-0.5">
                        <AlertTriangle size={10} /> {err}
                      </p>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ── Root export ───────────────────────────────────────────────────────────────

export function DespachoClient({
  activeTrips,
  completedRows,
}: {
  activeTrips: Trip[];
  completedRows: SettlementRow[];
}) {
  const [refreshKey, setRefreshKey] = useState(0);
  void refreshKey;

  return (
    <div className="flex flex-col gap-6">
      <section
        className="rounded-lg border border-border bg-surface overflow-hidden"
        aria-label="Viagens activas — emitir adiantamento"
      >
        <div className="px-4 py-3 border-b border-border bg-surface-2 flex items-center gap-2">
          <Clock size={14} className="text-amber" />
          <span className="text-[13px] font-semibold text-ink">
            Viagens Activas
          </span>
          <span className="ml-1 px-1.5 py-0.5 rounded text-[11px] font-mono bg-surface text-muted">
            {activeTrips.length}
          </span>
        </div>
        <ActiveTripsTable trips={activeTrips} />
      </section>

      <section
        className="rounded-lg border border-border bg-surface overflow-hidden"
        aria-label="Liquidações de viagens concluídas"
      >
        <div className="px-4 py-3 border-b border-border bg-surface-2 flex items-center gap-2">
          <BadgeCheck size={14} className="text-success" />
          <span className="text-[13px] font-semibold text-ink">
            Liquidações
          </span>
          <span className="ml-1 px-1.5 py-0.5 rounded text-[11px] font-mono bg-surface text-muted">
            {completedRows.length}
          </span>
        </div>
        <CompletedTripsTable
          rows={completedRows}
          onRefresh={() => setRefreshKey((k) => k + 1)}
        />
      </section>
    </div>
  );
}
