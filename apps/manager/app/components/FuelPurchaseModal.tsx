"use client";

import { useState, useEffect } from "react";
import { Plus, X } from "lucide-react";
import { ThirdPartyCombobox } from "./ThirdPartyCombobox";

interface VehicleOption {
  id: string;
  plate: string;
}

interface FuelPurchaseFormData {
  vehicle_id: string;
  liters: number;
  unit_cost: number;
  supplier_name: string;
  supplier_third_party_id: string | null;
  station: string;
  odometer_km: number | null;
  notes: string;
}

interface FuelPurchaseModalProps {
  /** Pre-loaded vehicle list. If omitted the modal fetches via /api/vehicles. */
  vehicleOptions?: VehicleOption[];
  onSuccess?: () => void;
}

export function FuelPurchaseModal({ vehicleOptions: vehicleOptionsProp, onSuccess }: FuelPurchaseModalProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Partial<FuelPurchaseFormData>>({
    supplier_third_party_id: null,
    supplier_name: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [vehicleOptions, setVehicleOptions] = useState<VehicleOption[]>(vehicleOptionsProp ?? []);

  // Fetch vehicles when the modal opens (only if not pre-loaded)
  useEffect(() => {
    if (!open || vehicleOptionsProp) return;
    fetch("/api/vehicles?limit=200", { cache: "no-store" })
      .then((r) => r.json())
      .then((data: unknown) => {
        const list = Array.isArray(data) ? data : [];
        setVehicleOptions(
          (list as Array<{ id: string; plate: string }>).map((v) => ({
            id: v.id,
            plate: v.plate,
          }))
        );
      })
      .catch(() => setVehicleOptions([]));
  }, [open, vehicleOptionsProp]);

  function resetForm() {
    setForm({ supplier_third_party_id: null, supplier_name: "" });
    setError(null);
  }

  function handleClose() {
    setOpen(false);
    resetForm();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/fuel-purchases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as {
          detail?: string;
          error?: { message?: string };
        };
        setError(body.error?.message ?? body.detail ?? "Erro ao registar abastecimento");
        return;
      }
      handleClose();
      if (onSuccess) {
        onSuccess();
      } else {
        window.location.reload();
      }
    } catch {
      setError("Erro de rede — tente novamente");
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: "8px 14px",
          background: "var(--amber)",
          color: "#fff",
          border: "none",
          borderRadius: "var(--r-md, 6px)",
          fontSize: "13px",
          fontWeight: 600,
          fontFamily: "Manrope, sans-serif",
          cursor: "pointer",
          transition: "background 80ms ease-out",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--amber-dark, #d97706)")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "var(--amber)")}
      >
        <Plus size={15} />
        Registar Abastecimento
      </button>
    );
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.5)",
        padding: 16,
      }}
    >
      <div
        style={{
          background: "var(--surface)",
          borderRadius: "var(--r-lg, 10px)",
          boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
          width: "100%",
          maxWidth: 520,
          padding: 24,
          fontFamily: "Manrope, sans-serif",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <h2 style={{ fontSize: "16px", fontWeight: 700, color: "var(--ink)", margin: 0 }}>
            Registar Abastecimento Externo
          </h2>
          <button
            type="button"
            onClick={handleClose}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--muted)",
              display: "flex",
              padding: 4,
            }}
          >
            <X size={18} />
          </button>
        </div>

        {error && (
          <div
            style={{
              background: "var(--error-bg, #fee2e2)",
              border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 6,
              padding: "8px 12px",
              fontSize: "13px",
              color: "var(--error, #dc2626)",
              marginBottom: 16,
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Vehicle */}
            <div>
              <label style={labelStyle}>Viatura *</label>
              <select
                required
                value={form.vehicle_id ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, vehicle_id: e.target.value }))}
                style={inputStyle}
              >
                <option value="">Seleccionar viatura</option>
                {vehicleOptions.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.plate}
                  </option>
                ))}
              </select>
            </div>

            {/* Supplier — ThirdPartyCombobox + free-text fallback */}
            <div>
              <ThirdPartyCombobox
                roleType="supplier"
                value={form.supplier_third_party_id ?? null}
                displayValue={form.supplier_name ?? null}
                label="Fornecedor (opcional)"
                placeholder="Seleccionar fornecedor registado..."
                onChange={(sel) => {
                  if (sel) {
                    setForm((f) => ({
                      ...f,
                      supplier_third_party_id: sel.id,
                      supplier_name: sel.name,
                    }));
                  } else {
                    setForm((f) => ({
                      ...f,
                      supplier_third_party_id: null,
                    }));
                  }
                }}
              />
              {/* Free-text fallback when no registered supplier selected */}
              {!form.supplier_third_party_id && (
                <input
                  type="text"
                  placeholder="Ou escrever nome do posto (texto livre)"
                  value={form.supplier_name ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, supplier_name: e.target.value }))}
                  style={{ ...inputStyle, marginTop: 8 }}
                />
              )}
            </div>

            {/* Liters + Unit cost */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label style={labelStyle}>Litros *</label>
                <input
                  required
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.liters ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, liters: parseFloat(e.target.value) }))
                  }
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Custo unitário (MZN) *</label>
                <input
                  required
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.unit_cost ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, unit_cost: parseFloat(e.target.value) }))
                  }
                  style={{ ...inputStyle, fontFamily: "IBM Plex Mono, monospace" }}
                />
              </div>
            </div>

            {/* Station + Odometer */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label style={labelStyle}>Posto / Estação</label>
                <input
                  type="text"
                  value={form.station ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, station: e.target.value }))}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Odómetro (km)</label>
                <input
                  type="number"
                  min="0"
                  value={form.odometer_km ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      odometer_km: e.target.value ? parseInt(e.target.value) : null,
                    }))
                  }
                  style={{ ...inputStyle, fontFamily: "IBM Plex Mono, monospace" }}
                />
              </div>
            </div>

            {/* Notes */}
            <div>
              <label style={labelStyle}>Observações</label>
              <textarea
                rows={2}
                value={form.notes ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                style={{ ...inputStyle, resize: "vertical", minHeight: 60 }}
              />
            </div>
          </div>

          {/* Actions */}
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 10,
              marginTop: 20,
              paddingTop: 16,
              borderTop: "1px solid var(--border)",
            }}
          >
            <button type="button" onClick={handleClose} style={ghostBtnStyle}>
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: "8px 18px",
                background: submitting ? "var(--muted)" : "var(--amber)",
                color: "#fff",
                border: "none",
                borderRadius: "var(--r-md, 6px)",
                fontSize: "13px",
                fontWeight: 600,
                fontFamily: "Manrope, sans-serif",
                cursor: submitting ? "not-allowed" : "pointer",
                transition: "background 80ms ease-out",
              }}
            >
              {submitting ? "A guardar..." : "Registar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Shared style tokens ───────────────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "11px",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "var(--muted)",
  marginBottom: 4,
  fontFamily: "Manrope, sans-serif",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  minHeight: "38px",
  padding: "0 10px",
  border: "1px solid var(--border-strong)",
  borderRadius: "var(--r-md, 6px)",
  background: "var(--surface)",
  color: "var(--ink)",
  fontSize: "13px",
  fontFamily: "Manrope, sans-serif",
  boxSizing: "border-box",
  outline: "none",
};

const ghostBtnStyle: React.CSSProperties = {
  padding: "8px 16px",
  background: "transparent",
  color: "var(--muted)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-md, 6px)",
  fontSize: "13px",
  fontFamily: "Manrope, sans-serif",
  cursor: "pointer",
};
