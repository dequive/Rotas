"use client";

import { AlertTriangle, Info, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";

/**
 * Actionable Error Modal — Intercepts backend 409/4xx/5xx errors and renders
 * a domain-specific CTA instead of a generic toast.
 *
 * 409 error codes are mapped to actionable suggestions so the receptionist
 * knows exactly what to do next.
 */

type ErrorCode =
  | "quantity_exceeds_approved_reservation"
  | "work_order_already_billed"
  | "payment_exceeds_invoice_balance"
  | "insufficient_permission"
  | "quote_already_converted"
  | string;

interface ActionableErrorModalProps {
  open: boolean;
  onClose: () => void;
  errorCode?: ErrorCode;
  errorMessage?: string;
  httpStatus?: number;
  /** Custom CTA to render at the bottom (overrides automatic mapping). */
  actionOverride?: React.ReactNode;
  /** Called when the user clicks the primary mapped action (e.g., "Criar Orçamento Suplementar"). */
  onAction?: (actionKey: string) => void;
}

interface ErrorMapping {
  title: string;
  description: string;
  icon: React.ReactNode;
  actionLabel: string;
  actionKey: string;
  variant: "warning" | "danger" | "info";
}

const ERROR_MAPPINGS: Record<string, ErrorMapping> = {
  quantity_exceeds_approved_reservation: {
    title: "Quantidade Excede Reserva Aprovada",
    description:
      "A quantidade solicitada excede o que foi aprovado no orçamento original. Crie um orçamento suplementar para cobrir a diferença.",
    icon: <AlertTriangle className="h-6 w-6 text-amber-500" />,
    actionLabel: "Criar Orçamento Suplementar",
    actionKey: "create_supplemental_quote",
    variant: "warning",
  },
  work_order_already_billed: {
    title: "Ordem de Serviço Já Faturada",
    description:
      "Esta OS já foi faturada e não pode ser alterada. Para modificações, anule a fatura primeiro ou crie um documento de crédito.",
    icon: <AlertTriangle className="h-6 w-6 text-rose-500" />,
    actionLabel: "Ver Fatura Vinculada",
    actionKey: "view_linked_invoice",
    variant: "danger",
  },
  payment_exceeds_invoice_balance: {
    title: "Pagamento Excede Saldo da Fatura",
    description:
      "O valor do pagamento é superior ao saldo em aberto desta fatura. Revise o valor ou registre como pagamento antecipado.",
    icon: <AlertTriangle className="h-6 w-6 text-amber-500" />,
    actionLabel: "Ajustar Valor",
    actionKey: "adjust_payment_amount",
    variant: "warning",
  },
  insufficient_permission: {
    title: "Permissão Insuficiente",
    description:
      "Não tem permissão para esta operação. Contacte o administrador do sistema para obter acesso.",
    icon: <AlertTriangle className="h-6 w-6 text-rose-500" />,
    actionLabel: "Contactar Administrador",
    actionKey: "contact_admin",
    variant: "danger",
  },
  quote_already_converted: {
    title: "Orçamento Já Convertido",
    description:
      "Este orçamento já foi aceite e convertido numa Ordem de Serviço. Não é possível aceitá-lo novamente.",
    icon: <Info className="h-6 w-6 text-blue-500" />,
    actionLabel: "Ver Ordem de Serviço",
    actionKey: "view_work_order",
    variant: "info",
  },
};

const DEFAULT_MAPPING: ErrorMapping = {
  title: "Erro Inesperado",
  description:
    "Ocorreu um erro inesperado no sistema. Se o problema persistir, contacte o suporte técnico.",
  icon: <AlertTriangle className="h-6 w-6 text-rose-500" />,
  actionLabel: "Tentar Novamente",
  actionKey: "retry",
  variant: "danger",
};

const VARIANT_STYLES = {
  warning: {
    border: "border-amber-500/30",
    bg: "bg-amber-500/5",
    button: "bg-amber-600 hover:bg-amber-700 text-white",
  },
  danger: {
    border: "border-rose-500/30",
    bg: "bg-rose-500/5",
    button: "bg-rose-600 hover:bg-rose-700 text-white",
  },
  info: {
    border: "border-blue-500/30",
    bg: "bg-blue-500/5",
    button: "bg-blue-600 hover:bg-blue-700 text-white",
  },
};

export function ActionableErrorModal({
  open,
  onClose,
  errorCode,
  errorMessage,
  httpStatus,
  actionOverride,
  onAction,
}: ActionableErrorModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  const mapping = errorCode && ERROR_MAPPINGS[errorCode]
    ? ERROR_MAPPINGS[errorCode]
    : DEFAULT_MAPPING;

  const style = VARIANT_STYLES[mapping.variant];

  const handleAction = useCallback(() => {
    onAction?.(mapping.actionKey);
    onClose();
  }, [mapping.actionKey, onAction, onClose]);

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      className="fixed inset-0 z-50 m-auto w-full max-w-md rounded-xl border border-border bg-card p-0 shadow-2xl backdrop:bg-black/60 backdrop:backdrop-blur-sm"
      onCancel={onClose}
    >
      <div className="relative p-6">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          aria-label="Fechar"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Icon + Title */}
        <div className="flex items-start gap-4 mb-4">
          <div className={`flex-shrink-0 rounded-full p-2.5 ${style.bg} ${style.border} border`}>
            {mapping.icon}
          </div>
          <div>
            <h3 className="text-base font-semibold text-foreground leading-tight">
              {mapping.title}
            </h3>
            {httpStatus && (
              <span className="text-xs text-muted-foreground font-mono">
                HTTP {httpStatus}
                {errorCode ? ` · ${errorCode}` : ""}
              </span>
            )}
          </div>
        </div>

        {/* Description */}
        <p className="text-sm text-muted-foreground leading-relaxed mb-2">
          {mapping.description}
        </p>

        {/* Original error message (when different from mapping description) */}
        {errorMessage && errorMessage !== mapping.description && (
          <div className="mt-2 rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground font-mono leading-relaxed">
            {errorMessage}
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-input bg-background hover:bg-accent transition-colors text-foreground"
          >
            Fechar
          </button>
          {actionOverride ?? (
            <button
              onClick={handleAction}
              className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${style.button}`}
            >
              {mapping.actionKey === "retry" && <RefreshCw className="h-4 w-4" />}
              {mapping.actionLabel}
            </button>
          )}
        </div>
      </div>
    </dialog>
  );
}
