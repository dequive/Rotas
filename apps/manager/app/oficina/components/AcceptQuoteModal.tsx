"use client";

import { Check, Loader2, MessageCircle, Pen, Phone, Users } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * AcceptQuoteModal — Traceable commercial consent for quote acceptance.
 *
 * Captures:
 *  - acceptance_channel: how the client confirmed (presencial, whatsapp, telefone, assinatura_digital)
 *  - accepted_by_person_name: who authorized (free text, required)
 *
 * Both fields are persisted on WorkshopQuote via the backend's `QuoteAcceptRequest`.
 */

interface AcceptQuoteModalProps {
  open: boolean;
  onClose: () => void;
  quoteNumber: string;
  totalAmount: number;
  /** Called with acceptance data when the user confirms */
  onAccept: (data: {
    acceptance_channel: string;
    accepted_by_person_name: string;
  }) => Promise<void>;
}

const CHANNELS = [
  { key: "presencial", label: "Presencial", icon: Users, description: "Cliente assinou em pessoa" },
  { key: "whatsapp", label: "WhatsApp", icon: MessageCircle, description: "Aprovação via mensagem" },
  { key: "telefone", label: "Telefone", icon: Phone, description: "Confirmação por chamada" },
  { key: "assinatura_digital", label: "Assinatura Digital", icon: Pen, description: "Assinatura electrónica" },
] as const;

export function AcceptQuoteModal({
  open,
  onClose,
  quoteNumber,
  totalAmount,
  onAccept,
}: AcceptQuoteModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [channel, setChannel] = useState<string>("");
  const [personName, setPersonName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) {
      el.showModal();
      // Reset state on open
      setChannel("");
      setPersonName("");
      setError(null);
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  const canSubmit = channel.length > 0 && personName.trim().length > 0 && !submitting;

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await onAccept({
        acceptance_channel: channel,
        accepted_by_person_name: personName.trim(),
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao aceitar orçamento.");
    } finally {
      setSubmitting(false);
    }
  }, [canSubmit, channel, personName, onAccept, onClose]);

  if (!open) return null;

  const formattedAmount = new Intl.NumberFormat("pt-MZ", {
    style: "decimal",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(totalAmount);

  return (
    <dialog
      ref={dialogRef}
      className="fixed inset-0 z-50 m-auto w-full max-w-lg rounded-xl border border-border bg-card p-0 shadow-2xl backdrop:bg-black/60 backdrop:backdrop-blur-sm"
      onCancel={onClose}
    >
      <div className="p-6 space-y-5">
        {/* Header */}
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            Aceitar Orçamento
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Confirme os dados de aprovação comercial antes de converter em Ordem de Serviço.
          </p>
        </div>

        {/* Quote summary card */}
        <div className="rounded-lg border border-border bg-muted/30 p-4 flex items-center justify-between">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">
              Orçamento
            </div>
            <div className="text-base font-mono font-semibold text-foreground mt-0.5">
              {quoteNumber}
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">
              Valor Total
            </div>
            <div className="text-base font-mono font-semibold text-emerald-600 mt-0.5">
              {formattedAmount} MT
            </div>
          </div>
        </div>

        {/* Channel selector */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">
            Canal de Aprovação <span className="text-rose-500">*</span>
          </label>
          <div className="grid grid-cols-2 gap-2">
            {CHANNELS.map((ch) => {
              const Icon = ch.icon;
              const selected = channel === ch.key;
              return (
                <button
                  key={ch.key}
                  onClick={() => setChannel(ch.key)}
                  className={`flex items-center gap-3 rounded-lg border p-3 text-left transition-all ${
                    selected
                      ? "border-primary bg-primary/5 ring-2 ring-primary/20"
                      : "border-border bg-background hover:bg-muted/40 hover:border-muted-foreground/30"
                  }`}
                >
                  <div
                    className={`rounded-full p-2 ${
                      selected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className={`text-sm font-medium ${selected ? "text-foreground" : "text-muted-foreground"}`}>
                      {ch.label}
                    </div>
                    <div className="text-[11px] text-muted-foreground">{ch.description}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Person name */}
        <div className="space-y-2">
          <label htmlFor="accepted_by_person_name" className="text-sm font-medium text-foreground">
            Nome de Quem Autorizou <span className="text-rose-500">*</span>
          </label>
          <input
            id="accepted_by_person_name"
            type="text"
            value={personName}
            onChange={(e) => setPersonName(e.target.value)}
            placeholder="Ex: João Silva, Director de Frota"
            className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          />
          <p className="text-[11px] text-muted-foreground">
            Nome e cargo da pessoa que autorizou a reparação (obrigatório para rastreabilidade).
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 px-3 py-2 text-sm text-rose-500">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-2 border-t border-border">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-input bg-background hover:bg-accent transition-colors text-foreground disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                A processar…
              </>
            ) : (
              <>
                <Check className="h-4 w-4" />
                Aceitar e Gerar OS
              </>
            )}
          </button>
        </div>
      </div>
    </dialog>
  );
}
