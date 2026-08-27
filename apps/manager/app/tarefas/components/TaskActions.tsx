"use client";

import { CheckCircle, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { bffFetch } from "@/app/lib/bff";

interface TaskActionsProps {
  taskId: string;
  source: "workshop" | "governance";
  currentStatus: string;
}

export function TaskActions({ taskId, source, currentStatus }: TaskActionsProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isCompleted = currentStatus === "completed" || currentStatus === "closed" || currentStatus === "resolved";
  const governanceTarget = currentStatus === "resolved" ? "closed" : "resolved";

  async function handleComplete() {
    setLoading(true);
    setError("");
    try {
      if (source === "workshop") {
        await bffFetch(`/api/v1/workshop/maintenance-requests/${taskId}/status`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "closed" })
        });
      } else {
        const reason = "Concluído via Central de Tarefas";
        await bffFetch(`/api/governance/cases/${taskId}/transitions`, {
          path: `/api/governance/cases/${taskId}/transitions`,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            to_status: governanceTarget,
            reason,
            payload: governanceTarget === "resolved" ? { resolution_note: reason } : {},
          })
        });
      }
      router.refresh();
    } catch (error) {
      console.error("Error completing task", error);
      setError(
        source === "governance"
          ? "Não foi possível atualizar o caso. A transição pode exigir dados ou anexos adicionais."
          : "Não foi possível encerrar o pedido de manutenção.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {(!isCompleted || (source === "governance" && currentStatus === "resolved")) && (
        <button 
          onClick={handleComplete}
          disabled={loading}
          className="flex items-center justify-center gap-2 w-full py-2 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg font-medium hover:bg-emerald-100 transition-colors text-sm disabled:opacity-50"
        >
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <CheckCircle size={16} />}
          {source === "governance"
            ? governanceTarget === "closed" ? "Fechar caso" : "Resolver caso"
            : "Encerrar pedido"}
        </button>
      )}
      {error && <p role="alert" className="rounded-lg bg-error-bg p-3 text-sm text-error">{error}</p>}
    </div>
  );
}
