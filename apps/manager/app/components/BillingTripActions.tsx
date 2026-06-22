"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Download } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";

import type { BillingTrip, ContractOption } from "../lib/billing-api";
import {
  createBillingWaiver,
  approveBillingWaiver,
  rejectBillingWaiver,
  enqueueExportJob,
  getJobStatus,
  getJobDownloadUrl,
} from "../lib/billing-api";

interface ApiConfig {
  apiBaseUrl: string;
  tenantId: string | null;
  token: string;
}

interface BillingTripActionsProps {
  trip: BillingTrip;
  contracts: ContractOption[];
  apiConfig: ApiConfig;
  /** User role for RBAC — owner/admin can approve waivers */
  userRole?: string;
  /** Billing document ID associated with this trip (for export actions) */
  documentId?: string;
}

type ExportState = "idle" | "polling" | "done" | "failed";
interface ExportJobState {
  status: ExportState;
  jobId?: string;
  format?: "pdf" | "xlsx";
}

export function BillingTripActions({
  trip,
  contracts,
  apiConfig,
  userRole,
  documentId,
}: BillingTripActionsProps) {
  const router = useRouter();
  const [contractId, setContractId] = useState(contracts[0]?.id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Waiver request modal state ──────────────────────────────────────────────
  const [showWaiverRequest, setShowWaiverRequest] = useState(false);
  const [waiverReason, setWaiverReason] = useState("");
  const [waiverSubmitting, setWaiverSubmitting] = useState(false);
  const [waiverError, setWaiverError] = useState<string | null>(null);

  // ── Waiver approval modal state ─────────────────────────────────────────────
  const [showWaiverReview, setShowWaiverReview] = useState(false);
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  // ── Export polling state ────────────────────────────────────────────────────
  const [exportPdf, setExportPdf] = useState<ExportJobState>({ status: "idle" });
  const [exportXlsx, setExportXlsx] = useState<ExportJobState>({ status: "idle" });

  const canUseApi = Boolean(apiConfig.tenantId);
  const isAdminOrOwner = userRole === "owner" || userRole === "admin";
  const hasNegativeMargin =
    trip.actualMargin !== null &&
    trip.actualMargin !== undefined &&
    trip.actualMargin < 0;

  const selectedContract = useMemo(
    () => contracts.find((c) => c.id === contractId) ?? null,
    [contractId, contracts],
  );

  // ── Legacy callApi (for existing actions) ─────────────────────────────────
  async function callApi(path: string, body: unknown) {
    if (!apiConfig.tenantId) {
      setError("Configure ROTAS_TENANT_ID.");
      return null;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${apiConfig.apiBaseUrl}${path}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiConfig.token}`,
          "Content-Type": "application/json",
          "X-Tenant-Id": apiConfig.tenantId,
        },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const message =
          payload?.error?.message ?? payload?.detail ?? `API respondeu HTTP ${response.status}`;
        throw new Error(message);
      }
      router.refresh();
      return payload;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Operação falhou.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  // ── Waiver request ─────────────────────────────────────────────────────────
  async function handleWaiverSubmit() {
    if (waiverReason.length < 10) return;
    setWaiverSubmitting(true);
    setWaiverError(null);
    try {
      await createBillingWaiver(trip.id, waiverReason);
      setShowWaiverRequest(false);
      setWaiverReason("");
      router.refresh();
    } catch {
      setWaiverError(
        "Ocorreu um erro ao submeter o pedido. Verifique a ligação e tente novamente.",
      );
    } finally {
      setWaiverSubmitting(false);
    }
  }

  // ── Waiver approval / rejection ────────────────────────────────────────────
  async function handleWaiverApprove() {
    if (!trip.waiverId) return;
    setReviewSubmitting(true);
    setReviewError(null);
    try {
      await approveBillingWaiver(trip.waiverId);
      setShowWaiverReview(false);
      router.refresh();
    } catch {
      setReviewError("Não foi possível aprovar o waiver. Tente novamente.");
    } finally {
      setReviewSubmitting(false);
    }
  }

  async function handleWaiverReject() {
    if (!trip.waiverId) return;
    setReviewSubmitting(true);
    setReviewError(null);
    try {
      await rejectBillingWaiver(trip.waiverId);
      setShowWaiverReview(false);
      router.refresh();
    } catch {
      setReviewError("Não foi possível rejeitar o waiver. Tente novamente.");
    } finally {
      setReviewSubmitting(false);
    }
  }

  // ── Export polling ─────────────────────────────────────────────────────────
  async function handleExport(format: "pdf" | "xlsx") {
    const docId = documentId ?? trip.id;
    const setState = format === "pdf" ? setExportPdf : setExportXlsx;
    setState({ status: "polling", format });
    try {
      const { jobId } = await enqueueExportJob(docId, format);
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        if (attempts > 60) {
          clearInterval(poll);
          setState({ status: "failed", jobId, format });
          return;
        }
        try {
          const result = await getJobStatus(jobId);
          if (result.status === "done") {
            clearInterval(poll);
            setState({ status: "done", jobId, format });
          } else if (result.status === "failed") {
            clearInterval(poll);
            setState({ status: "failed", jobId, format });
          }
        } catch {
          clearInterval(poll);
          setState({ status: "failed", jobId, format });
        }
      }, 2000);
    } catch {
      setState({ status: "failed", format });
    }
  }

  function ExportButton({ format, state }: { format: "pdf" | "xlsx"; state: ExportJobState }) {
    const label = format === "pdf" ? "Exportar PDF" : "Exportar XLSX";
    if (state.status === "idle") {
      return (
        <Button variant="outline" size="sm" onClick={() => handleExport(format)} type="button">
          {label}
        </Button>
      );
    }
    if (state.status === "polling") {
      return (
        <div className="flex flex-col gap-0.5">
          <Button variant="outline" size="sm" disabled type="button">A gerar…</Button>
          <span className="text-muted text-xs">A processar exportação…</span>
        </div>
      );
    }
    if (state.status === "done" && state.jobId) {
      return (
        <a
          href={getJobDownloadUrl(state.jobId)}
          download
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-surface-2 text-ink text-sm font-medium hover:bg-surface-2 transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          Descarregar
        </a>
      );
    }
    return (
      <div className="flex flex-col gap-0.5">
        <Button variant="outline" size="sm" onClick={() => handleExport(format)} type="button">
          {label}
        </Button>
        <span className="text-error text-xs">
          Falha ao gerar. Clique para tentar novamente.
        </span>
      </div>
    );
  }

  if (!canUseApi) {
    return <span className="text-muted text-sm">Acções indisponíveis sem API</span>;
  }

  if (trip.status === "uncontracted") {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        <select
          aria-label="Contrato"
          value={contractId}
          onChange={(e) => setContractId(e.target.value)}
        >
          {contracts.length === 0 ? <option value="">Sem contratos</option> : null}
          {contracts.map((c) => (
            <option key={c.id} value={c.id}>
              {c.contractReference} · {c.clientName}
            </option>
          ))}
        </select>
        <Button
          disabled={busy || !selectedContract}
          onClick={() =>
            callApi(`/api/v1/trips/${trip.id}/associate-contract`, { contract_id: contractId })
          }
          type="button"
          variant="outline"
          size="sm"
        >
          Associar
        </Button>
        {error && <small>{error}</small>}
      </div>
    );
  }

  if (trip.status === "pending_delivery_validation") {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        <Button
          disabled={busy || !trip.deliveryProofId}
          onClick={() =>
            callApi(
              `/api/v1/trips/${trip.id}/delivery-proof/${trip.deliveryProofId}/validate`,
              { validation_method: "manual_review", notes: "Validado no dashboard do gestor." },
            )
          }
          type="button"
          variant="outline"
          size="sm"
        >
          Validar descarga
        </Button>
        {error && <small>{error}</small>}
      </div>
    );
  }

  if (trip.status === "billable") {
    return (
      <div className="flex flex-col gap-2">
        {/* Waiver badges */}
        {hasNegativeMargin && trip.waiverStatus !== "active" && (
          <div className="flex items-center gap-2 flex-wrap">
            {(!trip.waiverStatus || trip.waiverStatus === "rejected") && (
              <>
                <Badge className="bg-orange/10 text-orange border border-orange/30 font-semibold">
                  Margem negativa
                </Badge>
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => setShowWaiverRequest(true)}
                >
                  Solicitar waiver
                </Button>
              </>
            )}
            {trip.waiverStatus === "pending_approval" && (
              <>
                <Badge className="bg-blue/10 text-blue border border-blue/30 font-semibold">
                  Waiver pendente
                </Badge>
                {isAdminOrOwner && (
                  <Button
                    variant="outline"
                    size="sm"
                    type="button"
                    className="border-cyan text-cyan hover:bg-cyan/10"
                    onClick={() => setShowWaiverReview(true)}
                  >
                    Rever waiver
                  </Button>
                )}
              </>
            )}
            {trip.waiverStatus === "rejected" && (
              <Badge className="bg-error-bg text-error border border-error-border font-semibold">
                Rejeitado
              </Badge>
            )}
          </div>
        )}
        {trip.waiverStatus === "active" && (
          <Badge className="bg-green/10 text-green border border-green/20 font-semibold w-fit">
            Aprovado
          </Badge>
        )}

        {/* Billing action — only show if no negative margin or has active waiver */}
        {(!hasNegativeMargin || trip.waiverStatus === "active") && (
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              disabled={busy}
              onClick={() => {
                const period = billingPeriodFor(trip.deliveredAt);
                callApi("/api/v1/billing/documents", {
                  contract_id: trip.contractId,
                  client_name: trip.client,
                  contract_reference: trip.contractReference,
                  billing_period_start: period.start,
                  billing_period_end: period.end,
                  currency: "MZN",
                  trip_ids: [trip.id],
                }).then((doc) => {
                  if (doc?.id) {
                    callApi(`/api/v1/billing/documents/${doc.id}/issue`, {
                      issued_at: new Date().toISOString(),
                    });
                  }
                });
              }}
              type="button"
              variant="outline"
              size="sm"
            >
              Cobrar
            </Button>
            {error && <small>{error}</small>}
          </div>
        )}

        {/* Waiver request modal */}
        <Dialog open={showWaiverRequest} onOpenChange={setShowWaiverRequest}>
          <DialogContent className="max-w-[540px]">
            <DialogHeader>
              <DialogTitle>Solicitar waiver de margem negativa</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <p className="text-sm text-muted">
                <span className="font-semibold text-ink">{trip.route}</span>
                {trip.actualMargin !== null && trip.actualMargin !== undefined && (
                  <span className="text-error font-semibold ml-2">
                    Margem: {Number(trip.actualMargin).toLocaleString("pt-MZ")} MZN
                  </span>
                )}
              </p>
              <Textarea
                placeholder="Descreva o motivo da margem negativa e a justificação para prosseguir com a cobrança…"
                value={waiverReason}
                onChange={(e) => setWaiverReason(e.target.value)}
                rows={4}
                className="resize-none"
              />
              <p className="text-xs text-muted">
                Mínimo 10 caracteres ({waiverReason.length}/10)
              </p>
              {waiverError && <p className="text-error text-sm">{waiverError}</p>}
            </div>
            <DialogFooter>
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  setShowWaiverRequest(false);
                  setWaiverReason("");
                  setWaiverError(null);
                }}
                disabled={waiverSubmitting}
              >
                Abandonar pedido
              </Button>
              <Button
                type="button"
                disabled={waiverReason.length < 10 || waiverSubmitting}
                onClick={handleWaiverSubmit}
              >
                {waiverSubmitting ? "A submeter…" : "Submeter pedido"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Waiver review modal (owner/admin only) */}
        <Dialog open={showWaiverReview} onOpenChange={setShowWaiverReview}>
          <DialogContent className="max-w-[680px]">
            <DialogHeader>
              <DialogTitle>Rever pedido de waiver</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div className="bg-surface-2 rounded-md p-3 text-sm space-y-1">
                <p><span className="font-semibold text-muted">Rota:</span> {trip.route}</p>
                {trip.actualMargin !== null && trip.actualMargin !== undefined && (
                  <p>
                    <span className="font-semibold text-muted">Margem:</span>{" "}
                    <span className="text-error font-semibold">
                      {Number(trip.actualMargin).toLocaleString("pt-MZ")} MZN
                    </span>
                  </p>
                )}
                {trip.waiverReason && (
                  <p>
                    <span className="font-semibold text-muted">Justificação:</span>{" "}
                    {trip.waiverReason}
                  </p>
                )}
              </div>
              {reviewError && <p className="text-error text-sm">{reviewError}</p>}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                type="button"
                className="text-error border-error-border hover:bg-error-bg"
                disabled={reviewSubmitting}
                onClick={handleWaiverReject}
              >
                {reviewSubmitting ? "A processar…" : "Rejeitar waiver"}
              </Button>
              <Button
                type="button"
                disabled={reviewSubmitting}
                onClick={handleWaiverApprove}
              >
                {reviewSubmitting ? "A processar…" : "Aprovar waiver"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  if (trip.status === "billing_draft" || trip.status === "billed") {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        <ExportButton format="pdf" state={exportPdf} />
        <ExportButton format="xlsx" state={exportXlsx} />
      </div>
    );
  }

  return (
    <span className="text-muted text-sm">
      <Badge variant="outline">Sem acção</Badge>
    </span>
  );
}

function billingPeriodFor(deliveredAt: string) {
  const date =
    deliveredAt && deliveredAt !== "-" ? new Date(`${deliveredAt}T00:00:00Z`) : new Date();
  const start = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
  const end = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 1));
  return { start: start.toISOString(), end: end.toISOString() };
}
