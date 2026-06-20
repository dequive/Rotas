"use client";

import { useState } from "react";
import { Upload } from "lucide-react";

interface DocumentUploadModalProps {
  subjectType: "driver" | "vehicle" | "third_party" | "client" | "contract";
  subjectId: string;
  onSuccess?: () => void;
}

const DOCUMENT_TYPES = [
  { value: "license", label: "Carta de Condução" },
  { value: "passport", label: "Passaporte" },
  { value: "bi", label: "Bilhete de Identidade" },
  { value: "insurance", label: "Seguro" },
  { value: "inspection", label: "Inspecção" },
  { value: "commercial_register", label: "Registo Comercial" },
  { value: "nuit_certificate", label: "Certificado NUIT" },
  { value: "contract_copy", label: "Cópia de Contrato" },
  { value: "other", label: "Outro" },
];

export function DocumentUploadModal({ subjectType, subjectId, onSuccess }: DocumentUploadModalProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    document_type: "",
    document_number: "",
    issued_at: "",
    expiry_date: "",
    issuing_authority: "",
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/operational-documents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, subject_type: subjectType, subject_id: subjectId }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(body.detail ?? "Erro ao guardar documento");
        return;
      }
      setOpen(false);
      setForm({
        document_type: "",
        document_number: "",
        issued_at: "",
        expiry_date: "",
        issuing_authority: "",
        notes: "",
      });
      onSuccess?.();
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
          padding: "5px 12px",
          background: "var(--amber)",
          color: "#fff",
          borderRadius: "var(--r-md, 6px)",
          fontSize: "12px",
          fontWeight: 600,
          fontFamily: "Manrope, sans-serif",
          border: "none",
          cursor: "pointer",
        }}
      >
        <Upload size={13} />
        Upload Documento
      </button>
    );
  }

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "7px 10px",
    fontSize: "13px",
    fontFamily: "Manrope, sans-serif",
    border: "1px solid var(--border-strong)",
    borderRadius: "var(--r-md, 6px)",
    background: "var(--surface-2)",
    color: "var(--ink)",
    outline: "none",
    boxSizing: "border-box",
  };

  const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: "11px",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    color: "var(--muted)",
    fontFamily: "Manrope, sans-serif",
    marginBottom: 4,
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.50)",
      }}
    >
      <div
        style={{
          background: "var(--surface)",
          borderRadius: "var(--r-xl, 12px)",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
          width: "100%",
          maxWidth: 520,
          padding: 24,
          margin: "0 16px",
        }}
      >
        <h2
          style={{
            fontSize: "16px",
            fontWeight: 600,
            fontFamily: "Manrope, sans-serif",
            color: "var(--ink)",
            marginBottom: 16,
          }}
        >
          Registar Documento
        </h2>

        {error && (
          <p
            style={{
              fontSize: "13px",
              color: "var(--error, #ef4444)",
              fontFamily: "Manrope, sans-serif",
              marginBottom: 12,
              padding: "8px 12px",
              background: "rgba(239,68,68,0.08)",
              borderRadius: "var(--r-md, 6px)",
            }}
          >
            {error}
          </p>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Tipo de Documento *</label>
            <select
              required
              value={form.document_type}
              onChange={(e) => setForm((f) => ({ ...f, document_type: e.target.value }))}
              style={inputStyle}
            >
              <option value="">Seleccionar tipo</option>
              {DOCUMENT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            <div>
              <label style={labelStyle}>Número do documento</label>
              <input
                type="text"
                value={form.document_number}
                onChange={(e) => setForm((f) => ({ ...f, document_number: e.target.value }))}
                style={{ ...inputStyle, fontFamily: "IBM Plex Mono, monospace" }}
                placeholder="Ex: 123456789"
              />
            </div>
            <div>
              <label style={labelStyle}>Entidade emissora</label>
              <input
                type="text"
                value={form.issuing_authority}
                onChange={(e) => setForm((f) => ({ ...f, issuing_authority: e.target.value }))}
                style={inputStyle}
                placeholder="Ex: INATTER"
              />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            <div>
              <label style={labelStyle}>Data de emissão</label>
              <input
                type="date"
                value={form.issued_at}
                onChange={(e) => setForm((f) => ({ ...f, issued_at: e.target.value }))}
                style={{ ...inputStyle, fontFamily: "IBM Plex Mono, monospace" }}
              />
            </div>
            <div>
              <label style={labelStyle}>Data de validade</label>
              <input
                type="date"
                value={form.expiry_date}
                onChange={(e) => setForm((f) => ({ ...f, expiry_date: e.target.value }))}
                style={{ ...inputStyle, fontFamily: "IBM Plex Mono, monospace" }}
              />
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>Notas</label>
            <textarea
              rows={2}
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              style={{ ...inputStyle, resize: "vertical" as const }}
              placeholder="Observações opcionais"
            />
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button
              type="button"
              onClick={() => setOpen(false)}
              style={{
                padding: "7px 14px",
                border: "1px solid var(--border-strong)",
                borderRadius: "var(--r-md, 6px)",
                background: "var(--surface-2)",
                color: "var(--ink)",
                fontSize: "13px",
                fontWeight: 600,
                fontFamily: "Manrope, sans-serif",
                cursor: "pointer",
              }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: "7px 14px",
                border: "none",
                borderRadius: "var(--r-md, 6px)",
                background: submitting ? "var(--border)" : "var(--amber)",
                color: "#fff",
                fontSize: "13px",
                fontWeight: 600,
                fontFamily: "Manrope, sans-serif",
                cursor: submitting ? "not-allowed" : "pointer",
              }}
            >
              {submitting ? "A guardar..." : "Guardar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
