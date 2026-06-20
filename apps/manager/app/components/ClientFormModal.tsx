"use client";

import { Loader2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { ClientResponse } from "../lib/clients-api";
import { Button } from "@/app/components/ui/Button";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

async function getAuthHeaders(): Promise<Record<string, string>> {
  // In client components we cannot access httpOnly cookies directly.
  // The Next.js API route /api/clients proxies to the backend with auth headers.
  // But for this pattern we use the same route as ContractFormModal (/api/contracts).
  // Client-side fetch uses the /api/* proxy routes that inject auth server-side.
  return {};
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

  if (!open) return null;

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

      const res = await fetch(url, {
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
    <div className="modal-backdrop" onClick={() => onOpenChange(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{mode === "create" ? "Novo Cliente" : "Editar Cliente"}</h2>
          <button
            className="icon-btn"
            onClick={() => onOpenChange(false)}
            type="button"
            aria-label="Fechar"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {/* Nome comercial — full width */}
          <label>
            Nome comercial <span style={{ color: "var(--error)" }}>*</span>
            <input
              name="trading_name"
              defaultValue={client?.trading_name ?? ""}
              disabled={loading}
              placeholder="Nome comercial do cliente"
            />
            {fieldErrors.trading_name && (
              <span className="field-error" style={{ color: "var(--error)", fontSize: 12 }}>
                {fieldErrors.trading_name}
              </span>
            )}
          </label>

          {/* Nome legal — full width */}
          <label>
            Nome legal
            <input
              name="legal_name"
              defaultValue={client?.legal_name ?? ""}
              disabled={loading}
              placeholder="Nome legal completo (opcional)"
            />
          </label>

          {/* Row 1: NUIT + Telefone */}
          <div className="form-row">
            <label>
              NUIT <span style={{ color: "var(--error)" }}>*</span>
              <input
                name="nuit"
                defaultValue={client?.nuit ?? ""}
                disabled={loading}
                placeholder="000000000"
                pattern="[0-9]{9}"
                maxLength={9}
                className="font-mono"
                style={{ fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)" }}
              />
              {fieldErrors.nuit && (
                <span className="field-error" style={{ color: "var(--error)", fontSize: 12 }}>
                  {fieldErrors.nuit}
                </span>
              )}
            </label>
            <label>
              Telefone
              <input
                name="phone"
                defaultValue={client?.phone ?? ""}
                disabled={loading}
                placeholder="+258..."
                type="tel"
              />
            </label>
          </div>

          {/* Row 2: Morada — full width */}
          <label>
            Morada
            <input
              name="address"
              defaultValue={client?.address ?? ""}
              disabled={loading}
              placeholder="Rua, número..."
            />
          </label>

          {/* Row 3: Cidade + Email */}
          <div className="form-row">
            <label>
              Cidade
              <input
                name="city"
                defaultValue={client?.city ?? ""}
                disabled={loading}
                placeholder="Maputo"
              />
            </label>
            <label>
              Email
              <input
                name="email"
                type="email"
                defaultValue={client?.email ?? ""}
                disabled={loading}
                placeholder="faturacao@empresa.co.mz"
              />
            </label>
          </div>

          {/* Row 4: Prazo de pagamento + Limite de crédito */}
          <div className="form-row">
            <label>
              Prazo de pagamento <span style={{ color: "var(--error)" }}>*</span>
              <select
                name="payment_terms_days"
                defaultValue={String(client?.payment_terms_days ?? "30")}
                disabled={loading}
              >
                <option value="30">30 dias</option>
                <option value="45">45 dias</option>
                <option value="60">60 dias</option>
                <option value="90">90 dias</option>
              </select>
              {fieldErrors.payment_terms_days && (
                <span className="field-error" style={{ color: "var(--error)", fontSize: 12 }}>
                  {fieldErrors.payment_terms_days}
                </span>
              )}
            </label>
            <label>
              Limite de crédito (MZN)
              <input
                name="credit_limit"
                type="number"
                min="0"
                step="0.01"
                defaultValue={client?.credit_limit != null ? String(client.credit_limit) : ""}
                disabled={loading}
                placeholder="0 = sem limite"
              />
            </label>
          </div>

          {apiError && (
            <div className="form-error" style={{ color: "var(--error)", fontSize: 13 }}>
              {apiError}
            </div>
          )}

          <div className="modal-actions">
            {mode === "edit" && (
              <button
                type="button"
                className="action-btn"
                style={{ color: "var(--error)", marginRight: "auto" }}
                onClick={handleDeactivate}
                disabled={loading}
              >
                Desactivar cliente
              </button>
            )}
            <button
              type="button"
              className="secondary-btn"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Cancelar
            </button>
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
      </div>
    </div>
  );
}
