"use client";

import { useState } from "react";
import { Upload } from "lucide-react";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

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

const inputCls =
  "w-full px-2.5 py-1.5 border border-border-strong rounded-md bg-surface-2 text-ink text-[13px] focus:outline-none focus:border-focus focus:ring-2 focus:ring-focus-soft";
const labelCls = "block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1";

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

  function handleClose() {
    setOpen(false);
    setForm({
      document_type: "",
      document_number: "",
      issued_at: "",
      expiry_date: "",
      issuing_authority: "",
      notes: "",
    });
    setError(null);
  }

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
      handleClose();
      onSuccess?.();
    } catch {
      setError("Erro de rede — tente novamente");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 h-[34px] px-3 border-none rounded-md bg-amber text-white text-xs font-bold cursor-pointer hover:bg-amber-dark transition-colors duration-100"
      >
        <Upload size={13} />
        Upload Documento
      </button>

      <ModalDialog open={open} onClose={handleClose} title="Registar Documento">
        <div className="px-6 pb-6 pt-4 flex flex-col gap-3">
          {error && (
            <div className="px-3 py-2 bg-error-bg border border-error-border rounded-md text-[13px] text-error">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div>
              <label className={labelCls}>Tipo de Documento *</label>
              <select
                required
                value={form.document_type}
                onChange={(e) => setForm((f) => ({ ...f, document_type: e.target.value }))}
                className={inputCls}
              >
                <option value="">Seleccionar tipo</option>
                {DOCUMENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Número do documento</label>
                <input
                  type="text"
                  value={form.document_number}
                  onChange={(e) => setForm((f) => ({ ...f, document_number: e.target.value }))}
                  className={`${inputCls} font-mono`}
                  placeholder="Ex: 123456789"
                />
              </div>
              <div>
                <label className={labelCls}>Entidade emissora</label>
                <input
                  type="text"
                  value={form.issuing_authority}
                  onChange={(e) => setForm((f) => ({ ...f, issuing_authority: e.target.value }))}
                  className={inputCls}
                  placeholder="Ex: INATTER"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Data de emissão</label>
                <input
                  type="date"
                  value={form.issued_at}
                  onChange={(e) => setForm((f) => ({ ...f, issued_at: e.target.value }))}
                  className={`${inputCls} font-mono`}
                />
              </div>
              <div>
                <label className={labelCls}>Data de validade</label>
                <input
                  type="date"
                  value={form.expiry_date}
                  onChange={(e) => setForm((f) => ({ ...f, expiry_date: e.target.value }))}
                  className={`${inputCls} font-mono`}
                />
              </div>
            </div>

            <div>
              <label className={labelCls}>Notas</label>
              <textarea
                rows={2}
                value={form.notes}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                className={`${inputCls} resize-y`}
                placeholder="Observações opcionais"
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-border mt-1">
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-2 border border-border rounded-md bg-transparent text-muted text-[13px] font-semibold cursor-pointer hover:bg-surface-2 transition-colors"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 rounded-md bg-amber text-white border-none text-[13px] font-bold cursor-pointer hover:bg-amber-dark transition-colors disabled:bg-border disabled:cursor-not-allowed"
              >
                {submitting ? "A guardar..." : "Guardar"}
              </button>
            </div>
          </form>
        </div>
      </ModalDialog>
    </>
  );
}
