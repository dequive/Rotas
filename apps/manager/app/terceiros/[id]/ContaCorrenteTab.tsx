"use client";

import { useEffect, useState, useCallback } from "react";

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

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("rotas_access_token");
  const tenantId = localStorage.getItem("rotas_tenant_id");
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(tenantId ? { "X-Tenant-Id": tenantId } : {}),
  };
}

function getApiBase(): string {
  if (typeof window === "undefined") return "";
  return (
    localStorage.getItem("rotas_api_base_url") ??
    (process.env.NEXT_PUBLIC_ROTAS_API_BASE_URL ?? "")
  );
}

function fmt(v: string, currency = "MZN") {
  return parseFloat(v || "0").toLocaleString("pt-MZ", {
    style: "currency",
    currency,
  });
}

export default function ContaCorrenteTab({
  thirdPartyId,
}: {
  thirdPartyId: string;
}) {
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
        const res = await fetch(
          `${getApiBase()}/api/v1/third-party/${thirdPartyId}/account${query}`,
          { headers: getAuthHeaders() },
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
      const res = await fetch(
        `${getApiBase()}/api/v1/third-party/${thirdPartyId}/account/statement.pdf${query}`,
        { headers: getAuthHeaders() },
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
    <div
      style={{
        marginTop: 16,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--r-lg, 10px)",
        padding: 24,
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h2
          style={{
            fontSize: "16px",
            fontWeight: 600,
            fontFamily: "Manrope, sans-serif",
            color: "var(--ink)",
            margin: 0,
          }}
        >
          Conta Corrente
        </h2>
        <button
          onClick={handleExportPdf}
          disabled={exporting || loading}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 14px",
            borderRadius: "var(--r-md, 6px)",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            color: "var(--ink)",
            fontSize: "13px",
            fontFamily: "Manrope, sans-serif",
            fontWeight: 600,
            cursor: exporting || loading ? "not-allowed" : "pointer",
            opacity: exporting || loading ? 0.6 : 1,
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
          </svg>
          {exporting ? "A gerar..." : "Exportar PDF"}
        </button>
      </div>

      {/* Period filter */}
      <form
        onSubmit={handleFilter}
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: 10,
          marginBottom: 20,
          padding: "12px 16px",
          background: "var(--bg, #f9fafb)",
          borderRadius: "var(--r-md, 6px)",
          border: "1px solid var(--border)",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label
            style={{
              fontSize: "11px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--muted)",
              fontFamily: "Manrope, sans-serif",
            }}
          >
            De
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            style={{
              padding: "6px 10px",
              borderRadius: "var(--r-sm, 4px)",
              border: "1px solid var(--border)",
              fontSize: "13px",
              fontFamily: "IBM Plex Mono, monospace",
              color: "var(--ink)",
              background: "var(--surface)",
            }}
          />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label
            style={{
              fontSize: "11px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--muted)",
              fontFamily: "Manrope, sans-serif",
            }}
          >
            Até
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            style={{
              padding: "6px 10px",
              borderRadius: "var(--r-sm, 4px)",
              border: "1px solid var(--border)",
              fontSize: "13px",
              fontFamily: "IBM Plex Mono, monospace",
              color: "var(--ink)",
              background: "var(--surface)",
            }}
          />
        </div>
        <button
          type="submit"
          style={{
            padding: "7px 16px",
            borderRadius: "var(--r-md, 6px)",
            border: "none",
            background: "var(--amber, #f59e0b)",
            color: "#000",
            fontSize: "13px",
            fontFamily: "Manrope, sans-serif",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          Filtrar
        </button>
        {(dateFrom || dateTo) && (
          <button
            type="button"
            onClick={handleClear}
            style={{
              padding: "7px 12px",
              borderRadius: "var(--r-md, 6px)",
              border: "1px solid var(--border)",
              background: "transparent",
              color: "var(--muted)",
              fontSize: "13px",
              fontFamily: "Manrope, sans-serif",
              cursor: "pointer",
            }}
          >
            Limpar
          </button>
        )}
      </form>

      {loading && (
        <p style={{ fontSize: "13px", color: "var(--muted)", fontFamily: "Manrope, sans-serif" }}>
          A carregar...
        </p>
      )}

      {error && (
        <p style={{ fontSize: "13px", color: "var(--error, #ef4444)", fontFamily: "Manrope, sans-serif" }}>
          {error}
        </p>
      )}

      {!loading && !error && account && (
        <>
          {/* Balance hero */}
          <div
            style={{
              textAlign: "center",
              padding: "20px 16px",
              marginBottom: 20,
              borderRadius: "var(--r-lg, 10px)",
              background:
                balanceNum >= 0
                  ? "rgba(34,197,94,0.08)"
                  : "rgba(239,68,68,0.08)",
            }}
          >
            {account.opening_balance !== undefined && (
              <p
                style={{
                  fontSize: "11px",
                  color: "var(--muted)",
                  fontFamily: "Manrope, sans-serif",
                  marginBottom: 4,
                }}
              >
                Saldo abertura:{" "}
                <span style={{ fontFamily: "IBM Plex Mono, monospace", color: "var(--ink)" }}>
                  {fmt(account.opening_balance ?? "0")}
                </span>
              </p>
            )}
            <p
              style={{
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--muted)",
                marginBottom: 4,
                fontFamily: "Manrope, sans-serif",
              }}
            >
              SALDO {account.date_from || account.date_to ? "DO PERÍODO" : "TOTAL"}
            </p>
            <p
              style={{
                fontFamily: "IBM Plex Mono, monospace",
                fontSize: "36px",
                fontWeight: 500,
                color: balanceNum >= 0 ? "var(--success, #22c55e)" : "var(--error, #ef4444)",
                margin: 0,
              }}
            >
              {balanceNum >= 0 ? "+" : ""}
              {fmt(account.balance)}
            </p>
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                gap: 32,
                marginTop: 10,
                fontSize: "13px",
                color: "var(--muted)",
                fontFamily: "Manrope, sans-serif",
              }}
            >
              <span>
                Débitos:{" "}
                <span style={{ fontFamily: "IBM Plex Mono, monospace", color: "var(--ink)" }}>
                  {fmt(account.total_debits)}
                </span>
              </span>
              <span>
                Créditos:{" "}
                <span style={{ fontFamily: "IBM Plex Mono, monospace", color: "var(--ink)" }}>
                  {fmt(account.total_credits)}
                </span>
              </span>
            </div>
          </div>

          {/* Movements table */}
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "13px",
                fontFamily: "Manrope, sans-serif",
              }}
            >
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Data", "Tipo", "Origem", "Descrição", "Valor"].map(
                    (h, i) => (
                      <th
                        key={h}
                        style={{
                          padding: "8px 12px",
                          textAlign: i === 4 ? "right" : "left",
                          fontSize: "11px",
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                          color: "var(--muted)",
                        }}
                      >
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {account.entries.map((e) => (
                  <tr key={e.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td
                      style={{
                        padding: "10px 12px",
                        fontFamily: "IBM Plex Mono, monospace",
                        fontSize: "12px",
                        color: "var(--ink)",
                      }}
                    >
                      {e.entry_date}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          padding: "2px 8px",
                          borderRadius: 999,
                          fontSize: "11px",
                          fontWeight: 600,
                          background:
                            e.entry_type === "credit"
                              ? "rgba(34,197,94,0.10)"
                              : "rgba(239,68,68,0.10)",
                          color:
                            e.entry_type === "credit"
                              ? "var(--success, #22c55e)"
                              : "var(--error, #ef4444)",
                          fontFamily: "Manrope, sans-serif",
                        }}
                      >
                        <span
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background:
                              e.entry_type === "credit"
                                ? "var(--success, #22c55e)"
                                : "var(--error, #ef4444)",
                            flexShrink: 0,
                          }}
                        />
                        {e.entry_type === "credit" ? "Crédito" : "Débito"}
                      </span>
                    </td>
                    <td
                      style={{
                        padding: "10px 12px",
                        color: "var(--muted)",
                        fontSize: "12px",
                      }}
                    >
                      {SOURCE_LABELS[e.source_type] ?? e.source_type}
                    </td>
                    <td
                      style={{
                        padding: "10px 12px",
                        fontSize: "13px",
                        color: "var(--ink)",
                      }}
                    >
                      {e.description ?? "—"}
                    </td>
                    <td
                      style={{
                        padding: "10px 12px",
                        textAlign: "right",
                        fontFamily: "IBM Plex Mono, monospace",
                        fontWeight: 600,
                        fontSize: "13px",
                        color:
                          e.entry_type === "credit"
                            ? "var(--success, #22c55e)"
                            : "var(--error, #ef4444)",
                      }}
                    >
                      {e.entry_type === "credit" ? "+" : "-"}
                      {fmt(e.amount, e.currency || "MZN")}
                    </td>
                  </tr>
                ))}
                {account.entries.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      style={{
                        padding: "32px 12px",
                        textAlign: "center",
                        color: "var(--muted)",
                        fontSize: "13px",
                        fontFamily: "Manrope, sans-serif",
                      }}
                    >
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
