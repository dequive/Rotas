"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { bffRequest } from "@/app/lib/bff";
import { useState } from "react";
import type { ClientResponse } from "../lib/clients-api";
import { Button } from "@/app/components/ui/Button";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

const lbl = "flex flex-col gap-1.5 text-[13px] font-bold text-muted";
const inp = "min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-[14px] text-ink w-full focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20";
const row = "grid grid-cols-2 gap-3";
const actions = "flex justify-end gap-2.5 mt-1.5 pt-4 border-t border-border";

interface ClientFormModalProps {
  mode: "create" | "edit";
  client?: ClientResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

interface FormErrors {
  trading_name?: string;
  nuit?: string;
  payment_terms_days?: string;
}

export function ClientFormModal({
  mode,
  client,
  open,
  onOpenChange,
  onSuccess,
}: ClientFormModalProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FormErrors>({});

  function validate(fd: FormData): FormErrors {
    const errors: FormErrors = {};
    const tradingName = fd.get("trading_name") as string;
    const nuit = fd.get("nuit") as string;
    const paymentTerms = fd.get("payment_terms_days") as string;

    if (!tradingName?.trim()) {
      errors.trading_name = "O nome comercial é obrigatório.";
    }
    if (!nuit?.trim()) {
      errors.nuit = "O NUIT é obrigatório.";
    } else if (!/^\d{9}$/.test(nuit.trim())) {
      errors.nuit = "O NUIT deve ter 9 dígitos.";
    }
    if (!paymentTerms) {
      errors.payment_terms_days = "O prazo de pagamento é obrigatório.";
    }
    return errors;
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setApiError(null);

    const fd = new FormData(e.currentTarget);
    const errors = validate(fd);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setFieldErrors({});
    setLoading(true);

    const creditLimitRaw = fd.get("credit_limit") as string;
    const payload: Record<string, unknown> = {
      trading_name: (fd.get("trading_name") as string).trim(),
      nuit: (fd.get("nuit") as string).trim(),
      payment_terms_days: Number(fd.get("payment_terms_days")),
    };

    const legalName = (fd.get("legal_name") as string)?.trim();
    if (legalName) payload.legal_name = legalName;

    const address = (fd.get("address") as string)?.trim();
    if (address) payload.address = address;

    const city = (fd.get("city") as string)?.trim();
    if (city) payload.city = city;

    const phone = (fd.get("phone") as string)?.trim();
    if (phone) payload.phone = phone;

    const email = (fd.get("email") as string)?.trim();
    if (email) payload.email = email;

    if (creditLimitRaw !== "" && creditLimitRaw !== null) {
      payload.credit_limit = Number(creditLimitRaw);
    }

    try {
      const url =
        mode === "create"
          ? "/api/clients"
          : `/api/clients/${client!.id}`;
      const method = mode === "create" ? "POST" : "PATCH";

      const res = await bffRequest("", {
        path: url,
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await res.json().catch(() => ({}))) as { detail?: string; error?: { message?: string; code?: string } };
      if (!res.ok) {
        setApiError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao guardar cliente. Tente novamente.");
        return;
      }

      onOpenChange(false);
      onSuccess?.();
      router.refresh();
    } catch {
      setApiError("Erro ao guardar cliente. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeactivate() {
    if (!client) return;
    setLoading(true);
    setApiError(null);
    try {
      const res = await fetch(`/api/clients/${client.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: false }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string; error?: { message?: string; code?: string } };
        setApiError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao desactivar cliente. Tente novamente.");
        return;
      }
      onOpenChange(false);
      onSuccess?.();
      router.refresh();
    } catch {
      setApiError("Erro ao desactivar cliente. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ModalDialog open={open} onClose={() => onOpenChange(false)} title={mode === "create" ? "Novo Cliente" : "Editar Cliente"}>
      <form onSubmit={handleSubmit} className="px-6 pb-6 pt-4 flex flex-col gap-3.5">
        <label className={lbl}>
          Nome comercial <span className="text-error">*</span>
          <input
            name="trading_name"
            defaultValue={client?.trading_name ?? ""}
            disabled={loading}
            placeholder="Nome comercial do cliente"
            className={inp}
          />
          {fieldErrors.trading_name && (
            <span className="text-error text-xs">{fieldErrors.trading_name}</span>
          )}
        </label>

        <label className={lbl}>
          Nome legal
          <input
            name="legal_name"
            defaultValue={client?.legal_name ?? ""}
            disabled={loading}
            placeholder="Nome legal completo (opcional)"
            className={inp}
          />
        </label>

        <div className={row}>
          <label className={lbl}>
            NUIT <span className="text-error">*</span>
            <input
              name="nuit"
              defaultValue={client?.nuit ?? ""}
              disabled={loading}
              placeholder="000000000"
              pattern="[0-9]{9}"
              maxLength={9}
              className={`${inp} font-mono`}
            />
            {fieldErrors.nuit && (
              <span className="text-error text-xs">{fieldErrors.nuit}</span>
            )}
          </label>
          <label className={lbl}>
            Telefone
            <input
              name="phone"
              defaultValue={client?.phone ?? ""}
              disabled={loading}
              placeholder="+258..."
              type="tel"
              className={inp}
            />
          </label>
        </div>

        <label className={lbl}>
          Morada
          <input
            name="address"
            defaultValue={client?.address ?? ""}
            disabled={loading}
            placeholder="Rua, número..."
            className={inp}
          />
        </label>

        <div className={row}>
          <label className={lbl}>
            Cidade
            <input
              name="city"
              defaultValue={client?.city ?? ""}
              disabled={loading}
              placeholder="Maputo"
              className={inp}
            />
          </label>
          <label className={lbl}>
            Email
            <input
              name="email"
              type="email"
              defaultValue={client?.email ?? ""}
              disabled={loading}
              placeholder="faturacao@empresa.co.mz"
              className={inp}
            />
          </label>
        </div>

        <div className={row}>
          <label className={lbl}>
            Prazo de pagamento <span className="text-error">*</span>
            <select
              name="payment_terms_days"
              defaultValue={String(client?.payment_terms_days ?? "30")}
              disabled={loading}
              className={inp}
            >
              <option value="30">30 dias</option>
              <option value="45">45 dias</option>
              <option value="60">60 dias</option>
              <option value="90">90 dias</option>
            </select>
            {fieldErrors.payment_terms_days && (
              <span className="text-error text-xs">{fieldErrors.payment_terms_days}</span>
            )}
          </label>
          <label className={lbl}>
            Limite de crédito (MZN)
            <input
              name="credit_limit"
              type="number"
              min="0"
              step="0.01"
              defaultValue={client?.credit_limit != null ? String(client.credit_limit) : ""}
              disabled={loading}
              placeholder="0 = sem limite"
              className={inp}
            />
          </label>
        </div>

        {apiError && <div className="text-error text-[13px] m-0 bg-error-bg border border-error-border rounded-md px-3 py-2">{apiError}</div>}

        <div className={actions}>
          {mode === "edit" && (
            <button
              type="button"
              className="inline-flex items-center gap-1 h-[30px] px-2.5 bg-surface text-error border border-error-border rounded-md text-xs font-bold whitespace-nowrap cursor-pointer disabled:opacity-60 mr-auto"
              onClick={handleDeactivate}
              disabled={loading}
            >
              Desactivar cliente
            </button>
          )}
          <Button
            type="button"
            variant="secondary"
            onClick={() => onOpenChange(false)}
            disabled={loading}
          >
            Cancelar
          </Button>
          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                A guardar...
              </>
            ) : mode === "create" ? (
              "Guardar Cliente"
            ) : (
              "Guardar Alterações"
            )}
          </Button>
        </div>
      </form>
    </ModalDialog>
  );
}
