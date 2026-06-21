"use client";

import { useState } from "react";
import { Save, RefreshCw } from "lucide-react";
import { Button } from "@/app/components/ui/Button";

type DocumentProfile = {
  id: string;
  tenant_id: string;
  logo_file_id: string | null;
  legal_name: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  province: string | null;
  country: string;
  phone: string | null;
  email: string | null;
  website: string | null;
  bank_name: string | null;
  bank_account: string | null;
  bank_nib: string | null;
  invoice_prefix: string;
  invoice_seq_padding: number;
  invoice_start_seq: number;
  per_type_sequences: boolean;
  payment_conditions: string;
  invoice_footer: string | null;
  show_bank_details: boolean;
  show_logo: boolean;
};

type FormState = {
  legal_name: string;
  address_line1: string;
  address_line2: string;
  city: string;
  province: string;
  country: string;
  phone: string;
  email: string;
  website: string;
  bank_name: string;
  bank_account: string;
  bank_nib: string;
  invoice_prefix: string;
  invoice_seq_padding: number;
  invoice_start_seq: number;
  per_type_sequences: boolean;
  payment_conditions: string;
  invoice_footer: string;
  show_bank_details: boolean;
  show_logo: boolean;
};

function initForm(p: DocumentProfile | null): FormState {
  return {
    legal_name: p?.legal_name ?? "",
    address_line1: p?.address_line1 ?? "",
    address_line2: p?.address_line2 ?? "",
    city: p?.city ?? "",
    province: p?.province ?? "",
    country: p?.country ?? "Moçambique",
    phone: p?.phone ?? "",
    email: p?.email ?? "",
    website: p?.website ?? "",
    bank_name: p?.bank_name ?? "",
    bank_account: p?.bank_account ?? "",
    bank_nib: p?.bank_nib ?? "",
    invoice_prefix: p?.invoice_prefix ?? "",
    invoice_seq_padding: p?.invoice_seq_padding ?? 4,
    invoice_start_seq: p?.invoice_start_seq ?? 1,
    per_type_sequences: p?.per_type_sequences ?? false,
    payment_conditions: p?.payment_conditions ?? "Pronto",
    invoice_footer: p?.invoice_footer ?? "",
    show_bank_details: p?.show_bank_details ?? true,
    show_logo: p?.show_logo ?? true,
  };
}

const inputClass =
  "h-10 px-3 bg-surface border border-border rounded-md text-[14px] text-ink focus:outline-none focus:border-amber w-full";
const labelClass = "text-[12px] font-semibold text-muted uppercase tracking-wide mb-1";

export function EmpresaFormClient({ initialProfile }: { initialProfile: DocumentProfile | null }) {
  const [form, setForm] = useState<FormState>(() => initForm(initialProfile));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(false);

    const payload = {
      legal_name: form.legal_name || null,
      address_line1: form.address_line1 || null,
      address_line2: form.address_line2 || null,
      city: form.city || null,
      province: form.province || null,
      country: form.country || null,
      phone: form.phone || null,
      email: form.email || null,
      website: form.website || null,
      bank_name: form.bank_name || null,
      bank_account: form.bank_account || null,
      bank_nib: form.bank_nib || null,
      invoice_prefix: form.invoice_prefix || null,
      invoice_seq_padding: form.invoice_seq_padding,
      invoice_start_seq: form.invoice_start_seq,
      per_type_sequences: form.per_type_sequences,
      payment_conditions: form.payment_conditions || null,
      invoice_footer: form.invoice_footer || null,
      show_bank_details: form.show_bank_details,
      show_logo: form.show_logo,
    };

    try {
      const res = await fetch("/api/tenants/document-profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      if (!res.ok) {
        setError(body?.detail ?? body?.error ?? "Erro ao guardar perfil.");
        return;
      }
      setSuccess(true);
      setTimeout(() => setSuccess(false), 4000);
    } finally {
      setSaving(false);
    }
  }

  const paddedExample = form.invoice_prefix
    ? `${form.invoice_prefix} 2026/${"1".padStart(form.invoice_seq_padding, "0")}`
    : `2026/${"1".padStart(form.invoice_seq_padding, "0")}`;

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {error && (
        <div className="p-3 bg-error-bg border border-error-border text-error rounded-md text-[13px] font-medium">
          {error}
        </div>
      )}
      {success && (
        <div className="p-3 bg-success-bg border border-success-border text-success rounded-md text-[13px] font-medium">
          Perfil guardado com sucesso.
        </div>
      )}

      {/* ── Dados da Empresa ─────────────────────────────────────────── */}
      <section className="bg-surface border border-border rounded-lg p-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-base font-semibold m-0">Dados da Empresa</h2>
        </div>
        <div className="flex flex-col gap-4 mt-4">
          <div className="flex flex-col gap-1">
            <span className={labelClass}>Nome Legal</span>
            <input
              className={inputClass}
              placeholder="Ex: Transportes Moçambique Lda"
              value={form.legal_name}
              onChange={(e) => set("legal_name", e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <span className={labelClass}>Morada — Linha 1</span>
            <input
              className={inputClass}
              placeholder="Rua, número, bairro"
              value={form.address_line1}
              onChange={(e) => set("address_line1", e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <span className={labelClass}>Morada — Linha 2</span>
            <input
              className={inputClass}
              placeholder="Complemento (opcional)"
              value={form.address_line2}
              onChange={(e) => set("address_line2", e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Cidade</span>
              <input
                className={inputClass}
                placeholder="Maputo"
                value={form.city}
                onChange={(e) => set("city", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Província</span>
              <input
                className={inputClass}
                placeholder="Maputo"
                value={form.province}
                onChange={(e) => set("province", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>País</span>
              <input
                className={inputClass}
                value={form.country}
                onChange={(e) => set("country", e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Telefone</span>
              <input
                className={inputClass}
                type="tel"
                placeholder="+258 21 000 000"
                value={form.phone}
                onChange={(e) => set("phone", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Email</span>
              <input
                className={inputClass}
                type="email"
                placeholder="geral@empresa.co.mz"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <span className={labelClass}>Website</span>
            <input
              className={inputClass}
              type="url"
              placeholder="https://www.empresa.co.mz"
              value={form.website}
              onChange={(e) => set("website", e.target.value)}
            />
          </div>
        </div>
      </section>

      {/* ── Dados Bancários ──────────────────────────────────────────── */}
      <section className="bg-surface border border-border rounded-lg p-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-base font-semibold m-0">Dados Bancários</h2>
        </div>
        <div className="flex flex-col gap-4 mt-4">
          <div className="flex flex-col gap-1">
            <span className={labelClass}>Banco</span>
            <input
              className={inputClass}
              placeholder="Ex: BIM — Millennium bim"
              value={form.bank_name}
              onChange={(e) => set("bank_name", e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Número de Conta</span>
              <input
                className={`${inputClass} font-mono`}
                placeholder="0000000000"
                value={form.bank_account}
                onChange={(e) => set("bank_account", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>NIB</span>
              <input
                className={`${inputClass} font-mono`}
                placeholder="000300000000000000050"
                value={form.bank_nib}
                onChange={(e) => set("bank_nib", e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <span className={labelClass}>Condições de Pagamento</span>
            <input
              className={inputClass}
              placeholder="Pronto"
              value={form.payment_conditions}
              onChange={(e) => set("payment_conditions", e.target.value)}
            />
            <p className="text-[12px] text-muted mt-1">
              Aparece no cabeçalho dos documentos emitidos (ex: Pronto, 30 dias, 60 dias).
            </p>
          </div>
        </div>
      </section>

      {/* ── Numeração de Documentos ───────────────────────────────────── */}
      <section className="bg-surface border border-border rounded-lg p-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-base font-semibold m-0">Numeração de Documentos</h2>
        </div>
        <div className="flex flex-col gap-4 mt-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Prefixo</span>
              <input
                className={`${inputClass} font-mono uppercase`}
                maxLength={10}
                placeholder="FT"
                value={form.invoice_prefix}
                onChange={(e) => set("invoice_prefix", e.target.value.toUpperCase())}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Dígitos (padding)</span>
              <input
                className={`${inputClass} font-mono`}
                type="number"
                min={1}
                max={8}
                value={form.invoice_seq_padding}
                onChange={(e) => set("invoice_seq_padding", Number(e.target.value))}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Sequência Inicial</span>
              <input
                className={`${inputClass} font-mono`}
                type="number"
                min={1}
                value={form.invoice_start_seq}
                onChange={(e) => set("invoice_start_seq", Number(e.target.value))}
              />
            </div>
          </div>

          <div className="flex items-center gap-3 p-3 bg-surface-2 border border-border rounded-md">
            <span className="text-[12px] text-muted">Exemplo de numeração:</span>
            <span className="font-mono text-[14px] font-medium text-ink">{paddedExample}</span>
          </div>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="w-4 h-4 accent-amber"
              checked={form.per_type_sequences}
              onChange={(e) => set("per_type_sequences", e.target.checked)}
            />
            <span className="text-[14px] text-ink">Sequências separadas por tipo de documento</span>
          </label>
          {form.per_type_sequences && (
            <p className="text-[12px] text-muted -mt-2">
              Faturas, recibos e notas de crédito terão contadores independentes (FT 2026/0001, RC
              2026/0001, ...).
            </p>
          )}
        </div>
      </section>

      {/* ── Configurações de Exibição ────────────────────────────────── */}
      <section className="bg-surface border border-border rounded-lg p-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-base font-semibold m-0">Documentos — Exibição</h2>
        </div>
        <div className="flex flex-col gap-4 mt-4">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="w-4 h-4 accent-amber"
              checked={form.show_bank_details}
              onChange={(e) => set("show_bank_details", e.target.checked)}
            />
            <span className="text-[14px] text-ink">Mostrar dados bancários nos documentos</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="w-4 h-4 accent-amber"
              checked={form.show_logo}
              onChange={(e) => set("show_logo", e.target.checked)}
            />
            <span className="text-[14px] text-ink">Mostrar logótipo nos documentos</span>
          </label>

          <div className="flex flex-col gap-1">
            <span className={labelClass}>Rodapé dos Documentos</span>
            <textarea
              className="px-3 py-2 bg-surface border border-border rounded-md text-[14px] text-ink focus:outline-none focus:border-amber w-full resize-vertical"
              rows={3}
              placeholder="Texto opcional que aparece no rodapé de cada documento emitido"
              value={form.invoice_footer}
              onChange={(e) => set("invoice_footer", e.target.value)}
            />
          </div>
        </div>
      </section>

      {/* ── Ações ────────────────────────────────────────────────────── */}
      <div className="flex justify-end pb-6">
        <Button type="submit" variant="primary" disabled={saving}>
          {saving ? (
            <RefreshCw size={16} className="animate-spin" />
          ) : (
            <Save size={16} />
          )}
          {saving ? "A guardar..." : "Guardar Perfil"}
        </Button>
      </div>
    </form>
  );
}
