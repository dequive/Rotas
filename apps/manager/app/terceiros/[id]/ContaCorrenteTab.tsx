"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { bffRequest } from "@/app/lib/bff";

interface LedgerEntry {
  id: string;
  entry_type: "debit" | "credit";
  amount: string;
  currency: string;
  source_type: string;
  source_id: string | null;
  description: string | null;
  entry_date: string;
  created_at: string;
}

interface AccountData {
  third_party_id: string;
  total_debits: string;
  total_credits: string;
  balance: string;
  opening_balance?: string;
  date_from?: string;
  date_to?: string;
  entries: LedgerEntry[];
}

const SOURCE_LABELS: Record<string, string> = {
  manual_payment: "Pagamento manual",
  fuel_purchase: "Combustível",
  work_order: "Ordem de serviço",
  invoice: "Fatura",
  adjustment: "Ajuste",
};

function fmt(v: string, currency = "MZN") {
  return parseFloat(v || "0").toLocaleString("pt-MZ", {
    style: "currency",
    currency,
  });
}

const dateCls =
  "h-9 px-2.5 border border-border rounded-md text-[13px] font-mono text-ink bg-surface focus:outline-none focus:border-focus focus:ring-2 focus:ring-focus-soft";

export default function ContaCorrenteTab({ thirdPartyId }: { thirdPartyId: string }) {
  const [account, setAccount] = useState<AccountData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [exporting, setExporting] = useState(false);

  const fetchAccount = useCallback(
    async (from: string, to: string) => {
      setLoading(true);
      setError(null);
      try {
        const qs = new URLSearchParams();
        if (from) qs.set("date_from", from);
        if (to) qs.set("date_to", to);
        const query = qs.toString() ? `?${qs}` : "";
        const res = await bffRequest(
          `/api/v1/third-party/${thirdPartyId}/account${query}`,
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: AccountData = await res.json();
        setAccount(data);
      } catch {
        setError("Não foi possível carregar a conta corrente.");
      } finally {
        setLoading(false);
      }
    },
    [thirdPartyId],
  );

  useEffect(() => {
    fetchAccount("", "");
  }, [fetchAccount]);

  function handleFilter(e: React.FormEvent) {
    e.preventDefault();
    fetchAccount(dateFrom, dateTo);
  }

  function handleClear() {
    setDateFrom("");
    setDateTo("");
    fetchAccount("", "");
  }

  async function handleExportPdf() {
    setExporting(true);
    try {
      const qs = new URLSearchParams();
      if (dateFrom) qs.set("date_from", dateFrom);
      if (dateTo) qs.set("date_to", dateTo);
      const query = qs.toString() ? `?${qs}` : "";
      const res = await bffRequest(
        `/api/v1/third-party/${thirdPartyId}/account/statement.pdf${query}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `extrato-conta-corrente.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      alert("Erro ao gerar o extrato PDF.");
    } finally {
      setExporting(false);
    }
  }

  const balanceNum = parseFloat(account?.balance ?? "0");

  return (
    <div className="mt-4 bg-surface border border-border rounded-lg p-6">
      {/* Header row */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-base font-semibold text-ink m-0">Conta Corrente</h2>
        <button
          onClick={handleExportPdf}
          disabled={exporting || loading}
          className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-md border border-border bg-surface text-ink text-[13px] font-semibold cursor-pointer hover:bg-surface-2 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
          </svg>
          {exporting ? "A gerar..." : "Exportar PDF"}
        </button>
      </div>

      {/* Period filter */}
      <form
        onSubmit={handleFilter}
        className="flex items-end gap-2.5 mb-5 px-4 py-3 bg-surface-2 rounded-md border border-border"
      >
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold uppercase tracking-wide text-muted">De</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className={dateCls}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold uppercase tracking-wide text-muted">Até</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className={dateCls}
          />
        </div>
        <button
          type="submit"
          className="h-9 px-4 rounded-md border-none bg-amber text-ink text-[13px] font-bold cursor-pointer hover:bg-amber-dark transition-colors"
        >
          Filtrar
        </button>
        {(dateFrom || dateTo) && (
          <button
            type="button"
            onClick={handleClear}
            className="h-9 px-3 rounded-md border border-border bg-transparent text-muted text-[13px] cursor-pointer hover:bg-surface transition-colors"
          >
            Limpar
          </button>
        )}
      </form>

      {loading && <p className="text-[13px] text-muted">A carregar...</p>}
      {error && <p className="text-[13px] text-error">{error}</p>}

      {!loading && !error && account && (
        <>
          {/* Balance hero — bg color is dynamic based on balance sign */}
          <div
            className="text-center px-4 py-5 mb-5 rounded-lg"
            style={{
              background: balanceNum >= 0 ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
            }}
          >
            {account.opening_balance !== undefined && (
              <p className="text-[11px] text-muted mb-1">
                Saldo abertura:{" "}
                <span className="font-mono text-ink">{fmt(account.opening_balance ?? "0")}</span>
              </p>
            )}
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted mb-1">
              SALDO {account.date_from || account.date_to ? "DO PERÍODO" : "TOTAL"}
            </p>
            <p
              className={cn(
                "font-mono text-4xl font-medium m-0",
                balanceNum >= 0 ? "text-success" : "text-error",
              )}
            >
              {balanceNum >= 0 ? "+" : ""}
              {fmt(account.balance)}
            </p>
            <div className="flex justify-center gap-8 mt-2.5 text-[13px] text-muted">
              <span>
                Débitos:{" "}
                <span className="font-mono text-ink">{fmt(account.total_debits)}</span>
              </span>
              <span>
                Créditos:{" "}
                <span className="font-mono text-ink">{fmt(account.total_credits)}</span>
              </span>
            </div>
          </div>

          {/* Movements table */}
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border">
                  {["Data", "Tipo", "Origem", "Descrição", "Valor"].map((h, i) => (
                    <th
                      key={h}
                      className={cn(
                        "px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted",
                        i === 4 ? "text-right" : "text-left",
                      )}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {account.entries.map((e) => (
                  <tr key={e.id} className="border-b border-border">
                    <td className="px-3 py-2.5 font-mono text-xs text-ink">{e.entry_date}</td>
                    <td className="px-3 py-2.5">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold",
                          e.entry_type === "credit"
                            ? "bg-success-bg text-success"
                            : "bg-error-bg text-error",
                        )}
                      >
                        <span
                          className={cn(
                            "w-1.5 h-1.5 rounded-full flex-shrink-0",
                            e.entry_type === "credit" ? "bg-success" : "bg-error",
                          )}
                        />
                        {e.entry_type === "credit" ? "Crédito" : "Débito"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted">
                      {SOURCE_LABELS[e.source_type] ?? e.source_type}
                    </td>
                    <td className="px-3 py-2.5 text-ink">{e.description ?? "—"}</td>
                    <td
                      className={cn(
                        "px-3 py-2.5 text-right font-mono font-semibold text-[13px]",
                        e.entry_type === "credit" ? "text-success" : "text-error",
                      )}
                    >
                      {e.entry_type === "credit" ? "+" : "-"}
                      {fmt(e.amount, e.currency || "MZN")}
                    </td>
                  </tr>
                ))}
                {account.entries.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-8 text-center text-muted text-[13px]">
                      Sem movimentos no período seleccionado
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
