"use client";

import { CheckCircle, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { bffRequest } from "@/app/lib/bff";

interface TaskActionsProps {
  taskId: string;
  source: "workshop" | "governance";
  currentStatus: string;
}

export function TaskActions({ taskId, source, currentStatus }: TaskActionsProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const isCompleted = currentStatus === "completed" || currentStatus === "closed" || currentStatus === "resolved";

  async function handleComplete() {
    setLoading(true);
    try {
      if (source === "workshop") {
        await bffRequest(`/api/v1/workshop/maintenance-requests/${taskId}/status`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "closed" })
        });
      } else {
        await bffRequest(`/api/v1/governance/cases/${taskId}/transition`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ to_status: "resolved", reason: "Marcado como concluído via Central de Tarefas" })
        });
      }
      router.refresh();
    } catch (error) {
      console.error("Error completing task", error);
      alert("Erro ao concluir a tarefa.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {!isCompleted && (
        <button 
          onClick={handleComplete}
          disabled={loading}
          className="flex items-center justify-center gap-2 w-full py-2 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg font-medium hover:bg-emerald-100 transition-colors text-sm disabled:opacity-50"
        >
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <CheckCircle size={16} />}
          Marcar como Concluído
        </button>
      )}
      
      <button 
        disabled={loading || isCompleted}
        className="flex items-center justify-center gap-2 w-full py-2 bg-white text-slate-700 border border-slate-300 rounded-lg font-medium hover:bg-slate-50 transition-colors text-sm disabled:opacity-50"
      >
        Alterar Estado
      </button>
    </div>
  );
}
