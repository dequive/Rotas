"use client";

import { useEffect, useState, useCallback } from "react";

interface VehicleInsurancePolicy {
  id: string;
  policy_number: string;
  insurer: string;
  coverage_type: "civil_liability" | "comprehensive" | "cargo";
  premium_amount: number;
  valid_from: string;
  valid_until: string;
  notes: string | null;
  created_at: string;
}

interface InsuranceFormData {
  policy_number: string;
  insurer: string;
  coverage_type: string;
  premium_amount: string;
  valid_from: string;
  valid_until: string;
  notes: string;
}

const EMPTY_FORM: InsuranceFormData = {
  policy_number: "",
  insurer: "",
  coverage_type: "civil_liability",
  premium_amount: "",
  valid_from: "",
  valid_until: "",
  notes: "",
};

const COVERAGE_LABELS: Record<string, string> = {
  civil_liability: "Responsabilidade Civil",
  comprehensive: "Multirriscos",
  cargo: "Cargo",
};

function insuranceStatus(
  validUntil: string,
): "vigente" | "a_renovar" | "expirado" {
  const today = new Date();
  const expiry = new Date(validUntil);
  const days = Math.floor((expiry.getTime() - today.getTime()) / 86400000);
  if (days < 0) return "expirado";
  if (days <= 30) return "a_renovar";
  return "vigente";
}

function StatusDot({
  status,
}: {
  status: "vigente" | "a_renovar" | "expirado";
}) {
  const map = {
    vigente: {
      dot: "bg-green-500",
      label: "Vigente",
      text: "text-green-700",
    },
    a_renovar: {
      dot: "bg-amber-400",
      label: "A renovar",
      text: "text-amber-700",
    },
    expirado: {
      dot: "bg-red-500",
      label: "Expirado",
      text: "text-red-700",
    },
  };
  const { dot, label, text } = map[status];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${text}`}>
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return { "Content-Type": "application/json" };
  const token = localStorage.getItem("rotas_access_token");
  const tenantId = localStorage.getItem("rotas_tenant_id");
  return {
    "Content-Type": "application/json",
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

export default function InsuranceTab({ vehicleId }: { vehicleId: string }) {
  const [insurances, setInsurances] = useState<VehicleInsurancePolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<InsuranceFormData>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchInsurances = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${getApiBase()}/api/v1/vehicles/${vehicleId}/insurance`,
        { headers: getAuthHeaders(), cache: "no-store" },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: VehicleInsurancePolicy[] = await res.json();
      setInsurances(Array.isArray(data) ? data : []);
    } catch {
      setError("Não foi possível carregar as apólices.");
    } finally {
      setLoading(false);
    }
  }, [vehicleId]);

  useEffect(() => {
    void fetchInsurances();
  }, [fetchInsurances]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(
        `${getApiBase()}/api/v1/vehicles/${vehicleId}/insurance`,
        {
          method: "POST",
          headers: getAuthHeaders(),
          body: JSON.stringify({
            ...form,
            premium_amount: parseFloat(form.premium_amount),
          }),
        },
      );
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as {
          detail?: string;
          error?: { message?: string };
        };
        throw new Error(
          err.error?.message ?? err.detail ?? "Erro ao registar apólice",
        );
      }
      setShowModal(false);
      setForm(EMPTY_FORM);
      await fetchInsurances();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-[21px] font-extrabold text-ink">
          Apólices de Seguro
        </h2>
        <button
          onClick={() => {
            setShowModal(true);
            setError(null);
          }}
          className="px-4 py-2 text-sm font-semibold rounded-md text-white transition-colors"
          style={{
            background: "var(--amber, #f59e0b)",
            borderRadius: "var(--r-md)",
          }}
          onMouseEnter={(e) =>
            ((e.currentTarget as HTMLButtonElement).style.background =
              "var(--amber-dark, #d97706)")
          }
          onMouseLeave={(e) =>
            ((e.currentTarget as HTMLButtonElement).style.background =
              "var(--amber, #f59e0b)")
          }
        >
          + Registar Apólice
        </button>
      </div>

      {error && !showModal && (
        <p className="text-red-600 text-sm mb-3">{error}</p>
      )}

      {/* Policy list */}
      {loading ? (
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border-color)",
            borderRadius: "var(--r-lg, 8px)",
            padding: "32px",
            textAlign: "center",
            fontSize: "13px",
            color: "var(--muted-color)",
            fontFamily: "Manrope, sans-serif",
          }}
        >
          A carregar...
        </div>
      ) : insurances.length === 0 ? (
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border-color)",
            borderRadius: "var(--r-lg, 8px)",
            padding: "32px",
            textAlign: "center",
          }}
        >
          <p
            style={{
              fontWeight: 700,
              fontSize: "14px",
              color: "var(--ink)",
              marginBottom: 4,
              fontFamily: "Manrope, sans-serif",
            }}
          >
            Sem apólices registadas
          </p>
          <p
            style={{
              fontSize: "13px",
              color: "var(--muted-color)",
              fontFamily: "Manrope, sans-serif",
            }}
          >
            Clique em &ldquo;Registar Apólice&rdquo; para adicionar a primeira
            apólice.
          </p>
        </div>
      ) : (
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border-color)",
            borderRadius: "var(--r-lg, 8px)",
            overflow: "hidden",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "13px",
              fontFamily: "Manrope, sans-serif",
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid var(--border-color)",
                  background: "var(--surface-2)",
                }}
              >
                {[
                  { label: "Apólice", align: "left" },
                  { label: "Seguradora", align: "left" },
                  { label: "Cobertura", align: "left" },
                  { label: "Prémio (MZN)", align: "right" },
                  { label: "Validade", align: "left" },
                  { label: "Estado", align: "left" },
                ].map((h) => (
                  <th
                    key={h.label}
                    style={{
                      padding: "10px 14px",
                      textAlign: h.align as "left" | "right",
                      fontSize: "11px",
                      fontWeight: 600,
                      textTransform: "uppercase" as const,
                      letterSpacing: "0.05em",
                      color: "var(--muted-color)",
                    }}
                  >
                    {h.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {insurances.map((ins) => {
                const status = insuranceStatus(ins.valid_until);
                return (
                  <tr
                    key={ins.id}
                    style={{ borderBottom: "1px solid var(--border-color)" }}
                  >
                    <td
                      style={{
                        padding: "10px 14px",
                        fontFamily: "IBM Plex Mono, monospace",
                        fontSize: "12px",
                        color: "var(--ink)",
                      }}
                    >
                      {ins.policy_number}
                    </td>
                    <td
                      style={{
                        padding: "10px 14px",
                        fontSize: "13px",
                        color: "var(--ink)",
                      }}
                    >
                      {ins.insurer}
                    </td>
                    <td
                      style={{
                        padding: "10px 14px",
                        fontSize: "13px",
                        color: "var(--ink)",
                      }}
                    >
                      {COVERAGE_LABELS[ins.coverage_type] ?? ins.coverage_type}
                    </td>
                    <td
                      style={{
                        padding: "10px 14px",
                        textAlign: "right",
                        fontFamily: "IBM Plex Mono, monospace",
                        fontSize: "12px",
                        color: "var(--ink)",
                      }}
                    >
                      {ins.premium_amount.toLocaleString("pt-MZ", {
                        minimumFractionDigits: 2,
                      })}
                    </td>
                    <td
                      style={{
                        padding: "10px 14px",
                        fontFamily: "IBM Plex Mono, monospace",
                        fontSize: "12px",
                        color: "var(--ink)",
                      }}
                    >
                      {new Date(ins.valid_until).toLocaleDateString("pt-MZ")}
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      <StatusDot status={status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Policy Modal */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(15, 23, 42, 0.45)" }}
        >
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border-color)",
              borderRadius: "var(--r-xl, 12px)",
              boxShadow: "var(--shadow-md)",
              width: "100%",
              maxWidth: 560,
            }}
          >
            {/* Modal header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 24px",
                borderBottom: "1px solid var(--border-color)",
              }}
            >
              <h3
                style={{
                  fontSize: "16px",
                  fontWeight: 700,
                  fontFamily: "Manrope, sans-serif",
                  color: "var(--ink)",
                }}
              >
                Registar Apólice
              </h3>
              <button
                onClick={() => {
                  setShowModal(false);
                  setError(null);
                }}
                style={{
                  background: "none",
                  border: "none",
                  fontSize: "20px",
                  cursor: "pointer",
                  color: "var(--muted-color)",
                  lineHeight: 1,
                }}
              >
                ×
              </button>
            </div>

            {/* Modal form */}
            <form
              onSubmit={(e) => void handleSubmit(e)}
              style={{ padding: "20px 24px" }}
            >
              {error && (
                <p
                  style={{
                    color: "var(--error)",
                    fontSize: "13px",
                    marginBottom: 12,
                  }}
                >
                  {error}
                </p>
              )}

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 16,
                  marginBottom: 16,
                }}
              >
                <div>
                  <label style={labelStyle}>Número da Apólice</label>
                  <input
                    required
                    value={form.policy_number}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, policy_number: e.target.value }))
                    }
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Seguradora</label>
                  <input
                    required
                    value={form.insurer}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, insurer: e.target.value }))
                    }
                    style={inputStyle}
                  />
                </div>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 16,
                  marginBottom: 16,
                }}
              >
                <div>
                  <label style={labelStyle}>Cobertura</label>
                  <select
                    value={form.coverage_type}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, coverage_type: e.target.value }))
                    }
                    style={inputStyle}
                  >
                    <option value="civil_liability">
                      Responsabilidade Civil
                    </option>
                    <option value="comprehensive">Multirriscos</option>
                    <option value="cargo">Cargo</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Prémio Anual (MZN)</label>
                  <input
                    required
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.premium_amount}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        premium_amount: e.target.value,
                      }))
                    }
                    style={{
                      ...inputStyle,
                      fontFamily: "IBM Plex Mono, monospace",
                    }}
                  />
                </div>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 16,
                  marginBottom: 16,
                }}
              >
                <div>
                  <label style={labelStyle}>Válida De</label>
                  <input
                    required
                    type="date"
                    value={form.valid_from}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, valid_from: e.target.value }))
                    }
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Válida Até</label>
                  <input
                    required
                    type="date"
                    value={form.valid_until}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, valid_until: e.target.value }))
                    }
                    style={inputStyle}
                  />
                </div>
              </div>

              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Notas (opcional)</label>
                <textarea
                  rows={2}
                  value={form.notes}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, notes: e.target.value }))
                  }
                  style={{ ...inputStyle, resize: "vertical" }}
                />
              </div>

              {/* Footer actions */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 12,
                  paddingTop: 12,
                  borderTop: "1px solid var(--border-color)",
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    setError(null);
                    setForm(EMPTY_FORM);
                  }}
                  style={{
                    padding: "8px 16px",
                    fontSize: "13px",
                    fontWeight: 600,
                    fontFamily: "Manrope, sans-serif",
                    border: "1px solid var(--border-strong)",
                    borderRadius: "var(--r-md, 6px)",
                    background: "transparent",
                    color: "var(--muted-color)",
                    cursor: "pointer",
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{
                    padding: "8px 16px",
                    fontSize: "13px",
                    fontWeight: 600,
                    fontFamily: "Manrope, sans-serif",
                    border: "none",
                    borderRadius: "var(--r-md, 6px)",
                    background: "var(--amber, #f59e0b)",
                    color: "white",
                    cursor: submitting ? "not-allowed" : "pointer",
                    opacity: submitting ? 0.7 : 1,
                  }}
                >
                  {submitting ? "A guardar..." : "Registar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// Style constants (avoids repetition in JSX)
const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "11px",
  fontWeight: 600,
  color: "var(--muted-color)",
  marginBottom: 4,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  fontFamily: "Manrope, sans-serif",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  border: "1px solid var(--border-color)",
  borderRadius: "var(--r-md, 6px)",
  padding: "8px 12px",
  fontSize: "13px",
  background: "var(--surface)",
  color: "var(--ink)",
  boxSizing: "border-box",
  fontFamily: "Manrope, sans-serif",
};
