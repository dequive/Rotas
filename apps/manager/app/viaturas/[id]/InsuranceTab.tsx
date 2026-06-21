"use client";

import { useEffect, useState, useCallback } from "react";
import { ModalDialog } from "@/app/components/ui/ModalDialog";
import { cn } from "@/lib/utils";

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

function insuranceStatus(validUntil: string): "vigente" | "a_renovar" | "expirado" {
  const days = Math.floor((new Date(validUntil).getTime() - Date.now()) / 86400000);
  if (days < 0) return "expirado";
  if (days <= 30) return "a_renovar";
  return "vigente";
}

function StatusDot({ status }: { status: "vigente" | "a_renovar" | "expirado" }) {
  const map = {
    vigente: { dot: "bg-success", label: "Vigente", text: "text-success" },
    a_renovar: { dot: "bg-amber", label: "A renovar", text: "text-warning" },
    expirado: { dot: "bg-error", label: "Expirado", text: "text-error" },
  };
  const { dot, label, text } = map[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-semibold", text)}>
      <span className={cn("w-2 h-2 rounded-full", dot)} />
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

const inputCls =
  "w-full border border-border-strong rounded-md px-3 py-2 text-[13px] bg-surface text-ink focus:outline-none focus:border-amber focus:ring-2 focus:ring-amber/20 box-border";
const labelCls =
  "block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1";

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
        throw new Error(err.error?.message ?? err.detail ?? "Erro ao registar apólice");
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
        <h2 className="text-[21px] font-extrabold text-ink">Apólices de Seguro</h2>
        <button
          onClick={() => {
            setShowModal(true);
            setError(null);
          }}
          className="h-[38px] px-4 rounded-md bg-amber text-white text-[13px] font-bold border-none cursor-pointer hover:bg-amber-dark transition-colors duration-100"
        >
          + Registar Apólice
        </button>
      </div>

      {error && !showModal && <p className="text-error text-sm mb-3">{error}</p>}

      {loading ? (
        <div className="bg-surface border border-border rounded-lg px-8 py-8 text-center text-[13px] text-muted">
          A carregar...
        </div>
      ) : insurances.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg px-8 py-8 text-center">
          <p className="font-bold text-[14px] text-ink mb-1">Sem apólices registadas</p>
          <p className="text-[13px] text-muted">
            Clique em &ldquo;Registar Apólice&rdquo; para adicionar a primeira apólice.
          </p>
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                {[
                  { label: "Apólice", right: false },
                  { label: "Seguradora", right: false },
                  { label: "Cobertura", right: false },
                  { label: "Prémio (MZN)", right: true },
                  { label: "Validade", right: false },
                  { label: "Estado", right: false },
                ].map((h) => (
                  <th
                    key={h.label}
                    className={cn(
                      "px-3.5 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted",
                      h.right ? "text-right" : "text-left",
                    )}
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
                  <tr key={ins.id} className="border-b border-border">
                    <td className="px-3.5 py-2.5 font-mono text-xs text-ink">
                      {ins.policy_number}
                    </td>
                    <td className="px-3.5 py-2.5 text-ink">{ins.insurer}</td>
                    <td className="px-3.5 py-2.5 text-ink">
                      {COVERAGE_LABELS[ins.coverage_type] ?? ins.coverage_type}
                    </td>
                    <td className="px-3.5 py-2.5 text-right font-mono text-xs text-ink">
                      {ins.premium_amount.toLocaleString("pt-MZ", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-3.5 py-2.5 font-mono text-xs text-ink">
                      {new Date(ins.valid_until).toLocaleDateString("pt-MZ")}
                    </td>
                    <td className="px-3.5 py-2.5">
                      <StatusDot status={status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <ModalDialog
        open={showModal}
        onClose={() => {
          setShowModal(false);
          setError(null);
          setForm(EMPTY_FORM);
        }}
        title="Registar Apólice"
      >
        <form onSubmit={(e) => void handleSubmit(e)} className="px-6 pb-6 pt-4 flex flex-col gap-4">
          {error && (
            <p className="text-error text-[13px]">{error}</p>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>Número da Apólice</label>
              <input
                required
                value={form.policy_number}
                onChange={(e) => setForm((f) => ({ ...f, policy_number: e.target.value }))}
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>Seguradora</label>
              <input
                required
                value={form.insurer}
                onChange={(e) => setForm((f) => ({ ...f, insurer: e.target.value }))}
                className={inputCls}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>Cobertura</label>
              <select
                value={form.coverage_type}
                onChange={(e) => setForm((f) => ({ ...f, coverage_type: e.target.value }))}
                className={inputCls}
              >
                <option value="civil_liability">Responsabilidade Civil</option>
                <option value="comprehensive">Multirriscos</option>
                <option value="cargo">Cargo</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Prémio Anual (MZN)</label>
              <input
                required
                type="number"
                min="0"
                step="0.01"
                value={form.premium_amount}
                onChange={(e) => setForm((f) => ({ ...f, premium_amount: e.target.value }))}
                className={`${inputCls} font-mono`}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>Válida De</label>
              <input
                required
                type="date"
                value={form.valid_from}
                onChange={(e) => setForm((f) => ({ ...f, valid_from: e.target.value }))}
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>Válida Até</label>
              <input
                required
                type="date"
                value={form.valid_until}
                onChange={(e) => setForm((f) => ({ ...f, valid_until: e.target.value }))}
                className={inputCls}
              />
            </div>
          </div>

          <div>
            <label className={labelCls}>Notas (opcional)</label>
            <textarea
              rows={2}
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              className={`${inputCls} resize-y`}
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-border">
            <button
              type="button"
              onClick={() => {
                setShowModal(false);
                setError(null);
                setForm(EMPTY_FORM);
              }}
              className="px-4 py-2 text-[13px] font-semibold border border-border-strong rounded-md bg-transparent text-muted cursor-pointer hover:bg-surface-2 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-[13px] font-bold rounded-md bg-amber text-white border-none cursor-pointer hover:bg-amber-dark transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {submitting ? "A guardar..." : "Registar"}
            </button>
          </div>
        </form>
      </ModalDialog>
    </div>
  );
}
