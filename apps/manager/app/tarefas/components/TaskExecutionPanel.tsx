import { Wrench } from "lucide-react";
import Link from "next/link";

interface WorkOrderSummary {
  work_order_number?: string;
  status?: string;
  actual_cost?: number | string | null;
  estimated_cost?: number | string | null;
}

export function TaskExecutionPanel({
  source,
  initialWorkOrder = null,
}: {
  taskId: string;
  source: "workshop" | "governance";
  initialWorkOrder?: WorkOrderSummary | null;
}) {
  if (source !== "workshop") return null;

  if (!initialWorkOrder) {
    return (
      <div className="mt-6 rounded-xl border border-border bg-surface p-6">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-muted p-2 text-ink-muted">
            <Wrench aria-hidden="true" size={20} />
          </div>
          <div>
            <h3 className="font-semibold text-ink">Sem ordem de serviço associada</h3>
            <p className="mt-1 text-sm text-ink-muted">
              A Central de Tarefas não cria nem simula ordens de serviço. Faça a gestão operacional no módulo Oficina.
            </p>
            <Link
              href="/oficina/ordens-servico"
              className="mt-3 inline-flex min-h-11 items-center rounded-lg border border-border-strong px-4 text-sm font-medium text-ink hover:bg-muted"
            >
              Abrir ordens de serviço
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-6 rounded-xl border border-border bg-surface p-6">
      <div className="flex items-center justify-between gap-4">
        <h2 className="flex items-center gap-2 font-semibold text-ink">
          <Wrench aria-hidden="true" size={18} />
          Ordem de serviço associada
        </h2>
        <span className="font-mono text-sm text-ink-muted">
          {initialWorkOrder.work_order_number ?? "Sem referência"}
        </span>
      </div>
      <p className="mt-3 text-sm text-ink-muted">
        Estado: {initialWorkOrder.status ?? "não informado"}. Consulte a Oficina para executar transições, materiais e custos.
      </p>
    </div>
  );
}
