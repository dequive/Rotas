"use client";

import { useRouter } from "next/navigation";
import type { KeyboardEvent } from "react";
import { useState, useTransition } from "react";
import {
  AlertTriangle,
  CircleDollarSign,
  ClipboardList,
  LockKeyhole,
  Package,
  Wrench,
} from "lucide-react";

import { Button } from "@/app/components/ui/Button";
import { KpiCard } from "@/app/components/ui/KpiCard";
import { MonoCell } from "@/app/components/ui/MonoCell";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import type { WorkOrderDetail, WorkOrderProfitability } from "../../lib/workshop-api";
import {
  addLaborSession,
  completeWorkOrderTask,
  confirmWorkshopInvoice,
  issuePart,
  releaseVehicle,
  retryBilling,
  returnPart,
  transitionWorkOrder,
  type WorkOrderActionResult,
} from "../ordens-servico/[id]/actions";
import { LaborLogModal } from "./LaborLogModal";
import { PartIssueReturnModal } from "./PartIssueReturnModal";
import { TaskCompleteModal } from "./TaskCompleteModal";
import {
  VehicleReleaseModal,
  type VehicleReleasePayload,
} from "./VehicleReleaseModal";
import { WorkOrderTransitionModal } from "./WorkOrderTransitionModal";

const tabs = ["tasks", "parts", "profitability", "origin"] as const;
type Tab = (typeof tabs)[number];

function money(value: number) {
  return new Intl.NumberFormat("pt-MZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

function permissionsFor(role: string) {
  const elevated = role === "owner" || role === "admin";
  return {
    approve: elevated || role === "manager",
    execute: elevated || role === "manager" || role === "mechanic",
    parts: elevated || role === "manager",
    quality: elevated || role === "manager",
    close: elevated || role === "manager",
    finance: elevated || role === "manager",
  };
}

export function WorkOrderDetailClient({
  detail,
  profitability,
  role,
  userId,
}: {
  detail: WorkOrderDetail;
  profitability: WorkOrderProfitability | null;
  role: string;
  userId: string;
}) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("tasks");
  const [laborOpen, setLaborOpen] = useState(false);
  const [partsMode, setPartsMode] = useState<"issue" | "return" | null>(null);
  const [transitionKey, setTransitionKey] = useState<
    "approve" | "start" | "quality-check" | "close" | "confirm-invoice" | null
  >(null);
  const [taskToComplete, setTaskToComplete] = useState<
    WorkOrderDetail["tasks"][number] | null
  >(null);
  const [releaseOpen, setReleaseOpen] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const [pending, startTransition] = useTransition();
  const permission = permissionsFor(role);
  const wo = detail.work_order;

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, current: Tab) {
    const currentIndex = tabs.indexOf(current);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const next = tabs[nextIndex];
    setTab(next);
    event.currentTarget
      .closest('[role="tablist"]')
      ?.querySelector<HTMLButtonElement>(`#work-order-tab-${next}`)
      ?.focus();
  }

  function run(action: () => Promise<WorkOrderActionResult>, closeModal?: () => void) {
    setMessage(null);
    startTransition(async () => {
      const result = await action();
      if (!result.ok) {
        setMessage({ kind: "error", text: result.error });
        return;
      }
      closeModal?.();
      setMessage({ kind: "success", text: "Operação concluída." });
      router.refresh();
    });
  }

  function nextAction() {
    if (wo.status === "draft" && permission.approve) return { label: "Aprovar OS", key: "approve" as const };
    if (wo.status === "approved" && permission.execute) return { label: "Iniciar execução", key: "start" as const };
    if (wo.status === "in_progress" && permission.quality) return { label: "Enviar para QC", key: "quality-check" as const };
    if (wo.status === "quality_check" && permission.close) return { label: "Fechar OS", key: "close" as const };
    return null;
  }
  const action = nextAction();
  const transitionCopy = {
    approve: {
      title: "Aprovar ordem de serviço",
      description:
        "Confirme que o âmbito e os recursos da OS estão prontos para execução.",
      confirmLabel: "Aprovar OS",
      requireNotes: false,
      requestActualCost: false,
    },
    start: {
      title: "Iniciar execução",
      description:
        "A execução passa a aceitar sessões de mão-de-obra, consumo de peças e conclusão de tarefas.",
      confirmLabel: "Iniciar execução",
      requireNotes: false,
      requestActualCost: false,
    },
    "quality-check": {
      title: "Enviar para controlo de qualidade",
      description:
        "O backend bloqueará esta transição se existir qualquer tarefa incompleta ou ferramenta não devolvida.",
      confirmLabel: "Enviar para QC",
      requireNotes: true,
      requestActualCost: false,
    },
    close: {
      title: "Concluir controlo de qualidade",
      description:
        "O fecho consolida o custo real e agenda a criação do rascunho fiscal através do outbox.",
      confirmLabel: "Concluir QC e fechar OS",
      requireNotes: true,
      requestActualCost: true,
    },
    "confirm-invoice": {
      title: "Emitir fatura da oficina",
      description:
        "A emissão atribui o número fiscal sequencial e torna o documento imutável. Confirme os valores antes de continuar.",
      confirmLabel: "Emitir fatura",
      requireNotes: false,
      requestActualCost: false,
    },
  } as const;
  const selectedTransition = transitionKey
    ? transitionCopy[transitionKey]
    : null;
  const invoiceReadyForDelivery =
    wo.invoice_status === "issued" || wo.invoice_status === "paid";

  return (
    <div className="space-y-5">
      <section className="rounded-[var(--r-lg)] border border-border bg-surface p-5 shadow-card">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-mono text-2xl font-semibold text-ink">
                {wo.work_order_number}
              </h1>
              <StatusBadge status={wo.status} size="md" />
            </div>
            <p className="mt-1 text-sm text-muted">
              {detail.vehicle ? (
                <>
                  {`${detail.vehicle.brand ?? ""} ${detail.vehicle.model ?? ""} · `}
                  <MonoCell className="font-semibold text-ink">{detail.vehicle.plate}</MonoCell>
                </>
              ) : "Sem viatura"}{" "}
              · {detail.client.trading_name}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {wo.billing_status === "billing_failed" && permission.close && (
              <Button
                variant="destructive"
                disabled={pending}
                onClick={() => run(() => retryBilling(wo.id))}
              >
                Repetir faturação
              </Button>
            )}
            {wo.document_id &&
              wo.invoice_status === "draft" &&
              permission.finance && (
                <Button
                  variant="primary"
                  disabled={pending}
                  onClick={() => setTransitionKey("confirm-invoice")}
                >
                  Emitir fatura
                </Button>
              )}
            {wo.status === "closed" &&
              detail.reception &&
              invoiceReadyForDelivery &&
              permission.close && (
                <Button
                  variant="accent"
                  disabled={pending}
                  onClick={() => setReleaseOpen(true)}
                >
                  Confirmar entrega
                </Button>
              )}
            {action && (
              <Button
                disabled={pending}
                loading={pending}
                onClick={() => setTransitionKey(action.key)}
              >
                {action.label}
              </Button>
            )}
          </div>
        </div>
      </section>

      {(detail.blockers.incomplete_tasks > 0 || detail.blockers.unreturned_tools > 0) && (
        <div role="alert" className="flex gap-3 rounded-[var(--r-lg)] border border-warning-border bg-warning-bg p-4 text-warning">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <div className="text-sm">
            <p className="font-semibold">Bloqueadores operacionais</p>
            <p>{detail.blockers.incomplete_tasks} tarefa(s) incompleta(s) · {detail.blockers.unreturned_tools} ferramenta(s) por devolver.</p>
          </div>
        </div>
      )}

      {wo.billing_status === "billing_failed" && (
        <div role="alert" className="rounded-[var(--r-lg)] border border-error-border bg-error-bg p-4 text-sm text-error">
          <strong>Faturação pendente de reconciliação:</strong> {wo.billing_error ?? "Falha não especificada."}
        </div>
      )}
      {wo.status === "closed" &&
        detail.reception &&
        !invoiceReadyForDelivery && (
          <div className="rounded-[var(--r-lg)] border border-status-awaiting bg-status-awaiting-soft p-4 text-sm text-status-awaiting">
            <strong>Entrega bloqueada:</strong> a viatura só pode ser entregue
            depois de a fatura da oficina estar emitida. Estado atual:{" "}
            <StatusBadge status={wo.invoice_status ?? wo.billing_status} />
          </div>
        )}
      {message && (
        <div
          role={message.kind === "error" ? "alert" : "status"}
          className={`rounded-[var(--r-md)] border p-3 text-sm ${
            message.kind === "error"
              ? "border-error-border bg-error-bg text-error"
              : "border-success-border bg-success-bg text-success"
          }`}
        >
          {message.text}
        </div>
      )}

      <div role="tablist" aria-label="Detalhes da ordem de serviço" className="flex overflow-x-auto border-b border-border">
        {tabs.map((item) => (
          <button
            key={item}
            id={`work-order-tab-${item}`}
            type="button"
            role="tab"
            aria-selected={tab === item}
            aria-controls={`work-order-panel-${item}`}
            tabIndex={tab === item ? 0 : -1}
            onClick={() => setTab(item)}
            onKeyDown={(event) => handleTabKeyDown(event, item)}
            className={`min-h-11 whitespace-nowrap border-b-2 px-4 py-3 text-sm transition-colors ${
              tab === item
                ? "border-rotas-500 font-semibold text-rotas-600"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {item === "tasks" ? "Tarefas & Mão-de-obra" : item === "parts" ? "Peças" : item === "profitability" ? "Rentabilidade" : "Receção & Origem"}
          </button>
        ))}
      </div>

      {tab === "tasks" && (
        <section
          id="work-order-panel-tasks"
          role="tabpanel"
          aria-labelledby="work-order-tab-tasks"
          tabIndex={0}
          className="space-y-4"
        >
          <div className="flex justify-between">
            <h2 className="flex items-center gap-2 font-semibold"><ClipboardList className="h-4 w-4" /> Tarefas</h2>
            {permission.execute && wo.status === "in_progress" && (
              <Button variant="secondary" size="sm" onClick={() => setLaborOpen(true)}>
                Registar sessão
              </Button>
            )}
          </div>
          {detail.tasks.map((task) => (
            <article key={task.id} className="rounded-[var(--r-lg)] border border-border bg-surface p-4 shadow-card">
              <div className="flex justify-between gap-4">
                <div>
                  <p className="font-medium">{task.description}</p>
                  <p className="text-xs text-muted">{task.assigned_mechanic_name ?? "Sem mecânico atribuído"}</p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <StatusBadge status={task.status} />
                  {permission.execute &&
                    wo.status === "in_progress" &&
                    task.status !== "completed" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setTaskToComplete(task)}
                      >
                        Concluir tarefa
                      </Button>
                    )}
                </div>
              </div>
              <div className="mt-3 space-y-2">
                {task.labor_sessions.map((log) => <div key={log.id} className={`flex flex-wrap justify-between gap-2 rounded-[var(--r-sm)] bg-surface-2 p-2 text-xs ${log.voided_at ? "line-through opacity-60" : ""}`}><span>{log.mechanic_name} · {log.minutes_worked} min</span><MonoCell>{money(log.total_labor_cost)} MT {log.void_reason ? `· ${log.void_reason}` : ""}</MonoCell></div>)}
                {!task.labor_sessions.length && <p className="text-xs text-muted">Sem sessões registadas.</p>}
              </div>
            </article>
          ))}
        </section>
      )}

      {tab === "parts" && (
        <section
          id="work-order-panel-parts"
          role="tabpanel"
          aria-labelledby="work-order-tab-parts"
          tabIndex={0}
          className="space-y-4"
        >
          <div className="flex flex-wrap justify-between gap-2"><h2 className="flex items-center gap-2 font-semibold"><Package className="h-4 w-4" /> Consumo líquido</h2>{permission.parts && wo.status === "in_progress" && <div className="flex gap-2"><Button variant="secondary" size="sm" onClick={() => setPartsMode("issue")}>Entrega física</Button><Button variant="secondary" size="sm" onClick={() => setPartsMode("return")}>Devolver</Button></div>}</div>
          <div className="overflow-x-auto rounded-[var(--r-lg)] border border-border"><table className="w-full text-sm"><thead className="bg-surface-2 text-left"><tr><th className="p-3">Peça</th><th className="p-3 text-right">Emitido</th><th className="p-3 text-right">Devolvido</th><th className="p-3 text-right">Líquido</th><th className="p-3 text-right">Custo</th></tr></thead><tbody>{detail.parts_issued.map((part) => <tr key={part.inventory_id} className="border-t border-border"><td className="p-3"><MonoCell className="font-semibold">{part.sku}</MonoCell><br /><span className="text-xs text-muted">{part.name}</span></td><td className="p-3 text-right font-mono">{part.issued_quantity}</td><td className="p-3 text-right font-mono">{part.returned_quantity}</td><td className="p-3 text-right font-mono">{part.net_quantity} {part.unit}</td><td className="p-3 text-right font-mono">{money(part.net_cost)} MT</td></tr>)}</tbody></table></div>
          {!!detail.unreturned_tools.length && <div className="rounded-[var(--r-lg)] border border-warning-border bg-warning-bg p-4"><h3 className="mb-2 flex items-center gap-2 font-medium text-warning"><Wrench className="h-4 w-4" /> Ferramentas por devolver</h3>{detail.unreturned_tools.map((tool) => <p key={tool.checkout_id} className="text-sm"><MonoCell>{tool.code}</MonoCell> — {tool.name}</p>)}</div>}
        </section>
      )}

      {tab === "profitability" && (
        <section
          id="work-order-panel-profitability"
          role="tabpanel"
          aria-labelledby="work-order-tab-profitability"
          tabIndex={0}
          className="space-y-4"
        >
          <div className="flex items-center gap-2"><CircleDollarSign className="h-5 w-5" /><h2 className="font-semibold">Rentabilidade {wo.status === "closed" && wo.invoice_status ? "consolidada" : "preliminar"}</h2></div>
          {!permission.finance || !profitability ? <p className="rounded-[var(--r-lg)] border border-border p-4 text-sm text-muted">Sem permissão financeira ou dados indisponíveis.</p> : <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[["Receita", profitability.total_revenue, "primary"], ["Mão-de-obra", profitability.total_labor_cost, "default"], ["Peças líquidas", profitability.total_parts_cost, "default"], ["Margem bruta", profitability.gross_profit_mzn, profitability.gross_profit_mzn >= 0 ? "success" : "error"]].map(([label, value, semantic]) => <KpiCard key={String(label)} label={String(label)} value={`${money(Number(value))} MT`} semantic={semantic as "primary" | "default" | "success" | "error"} />)}</div>}
          <p className="text-xs text-muted">Estado da faturação: <StatusBadge status={wo.billing_status} />{wo.invoice_number ? <MonoCell className="ml-2">{wo.invoice_number}</MonoCell> : null}</p>
        </section>
      )}

      {tab === "origin" && (
        <section
          id="work-order-panel-origin"
          role="tabpanel"
          aria-labelledby="work-order-tab-origin"
          tabIndex={0}
          className="grid gap-4 lg:grid-cols-2"
        >
          <div className="rounded-[var(--r-lg)] border border-border bg-surface p-4 shadow-card"><h2 className="font-semibold">Receção</h2>{detail.reception ? <><p className="mt-2"><MonoCell>{detail.reception.reception_number}</MonoCell></p><p className="mt-2 text-sm text-muted">{detail.reception.reported_issues ?? "Sem ocorrências reportadas."}</p><div className="mt-3 flex flex-wrap gap-2">{detail.reception.photos.map((photo) => <a key={photo.id} className="min-h-11 rounded-[var(--r-md)] border border-border px-3 py-2 text-xs font-semibold text-rotas-600 hover:bg-rotas-50" href={`/api/files/${photo.file_id}/download`}>{photo.caption ?? "Fotografia"}</a>)}</div></> : <p className="mt-2 text-sm text-muted">OS sem receção associada.</p>}</div>
          <div className="rounded-[var(--r-lg)] border border-border bg-surface p-4 shadow-card"><h2 className="flex items-center gap-2 font-semibold">Orçamento {detail.quote?.status === "converted" && <LockKeyhole aria-label="Documento imutável" className="h-4 w-4 text-status-execution" />}</h2>{detail.quote ? <><p className="mt-2"><MonoCell>{detail.quote.quote_number}</MonoCell></p><p className="mt-2 text-sm">Valor aprovado: <MonoCell className="font-semibold">{money(detail.quote.approved_value)} MT</MonoCell></p><p className="mt-2"><StatusBadge status={detail.quote.status} /></p></> : <p className="mt-2 text-sm text-muted">OS sem orçamento associado.</p>}</div>
        </section>
      )}

      <LaborLogModal open={laborOpen} tasks={detail.tasks.filter((task) => task.status !== "completed")} defaultUserId={userId} busy={pending} onClose={() => setLaborOpen(false)} onSubmit={(taskId, mechanicId, minutes) => run(() => addLaborSession(taskId, mechanicId, minutes), () => setLaborOpen(false))} />
      <PartIssueReturnModal open={partsMode !== null} mode={partsMode ?? "issue"} parts={detail.parts_issued} busy={pending} onClose={() => setPartsMode(null)} onSubmit={(inventoryId, quantity, reason) => run(() => partsMode === "return" ? returnPart(wo.id, inventoryId, quantity, reason) : issuePart(wo.id, inventoryId, quantity, reason), () => setPartsMode(null))} />
      <TaskCompleteModal
        open={taskToComplete !== null}
        taskDescription={taskToComplete?.description ?? ""}
        defaultMinutes={
          taskToComplete?.actual_minutes ??
          taskToComplete?.estimated_minutes ??
          1
        }
        busy={pending}
        onClose={() => setTaskToComplete(null)}
        onConfirm={(minutes, notes) => {
          if (!taskToComplete) return;
          run(
            () =>
              completeWorkOrderTask(
                wo.id,
                taskToComplete.id,
                minutes,
                notes,
              ),
            () => setTaskToComplete(null),
          );
        }}
      />
      {selectedTransition && (
        <WorkOrderTransitionModal
          open={transitionKey !== null}
          title={selectedTransition.title}
          description={selectedTransition.description}
          confirmLabel={selectedTransition.confirmLabel}
          requireNotes={selectedTransition.requireNotes}
          requestActualCost={selectedTransition.requestActualCost}
          defaultActualCost={profitability?.total_cost ?? wo.actual_cost ?? 0}
          busy={pending}
          onClose={() => setTransitionKey(null)}
          onConfirm={(notes, actualCost) => {
            if (!transitionKey) return;
            if (transitionKey === "confirm-invoice") {
              if (!wo.document_id) return;
              run(
                () => confirmWorkshopInvoice(wo.document_id!),
                () => setTransitionKey(null),
              );
              return;
            }
            run(
              () =>
                transitionWorkOrder(
                  wo.id,
                  transitionKey,
                  notes,
                  actualCost,
                ),
              () => setTransitionKey(null),
            );
          }}
        />
      )}
      {detail.reception && detail.vehicle && (
        <VehicleReleaseModal
          open={releaseOpen}
          minimumOdometer={detail.vehicle.current_km}
          busy={pending}
          onClose={() => setReleaseOpen(false)}
          onConfirm={(payload: VehicleReleasePayload) =>
            run(
              () => releaseVehicle(detail.reception!.id, payload),
              () => setReleaseOpen(false),
            )
          }
        />
      )}
    </div>
  );
}
