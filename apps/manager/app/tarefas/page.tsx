import { getUnifiedTasks } from "@/app/lib/tarefas-api";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { ClipboardList, Plus, AlertCircle, Clock, CheckCircle2, Wrench } from "lucide-react";
import Link from "next/link";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { DataSourceBadge } from "@/app/components/ui/DataSourceBadge";
import { StatusBadge } from "@/app/components/ui/StatusBadge";

export const dynamic = "force-dynamic";

export default async function TarefasPage() {
  const { tasks, unavailableSources } = await getUnifiedTasks();

  return (
    <SidebarLayout active="tarefas">
      <div className="p-6 max-w-7xl mx-auto flex flex-col gap-6 h-full">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <ClipboardList className="text-amber" /> Central de Tarefas
            </h1>
            <p className="text-slate-500 mt-1">
              Gerencie todas as tarefas internas, desde ordens de manutenção da frota a pedidos de RH e TI.
            </p>
          </div>
          <Link
            href="/tarefas/nova"
            className="flex items-center gap-2 bg-amber text-ink px-4 py-2 rounded-lg font-semibold hover:bg-amber-dark transition-colors shadow-sm"
          >
            <Plus size={18} /> Nova Tarefa
          </Link>
        </div>

        <DataSourceBadge
          source={unavailableSources.length === 0 ? "api" : tasks.length > 0 ? "degraded" : "unavailable"}
          message={
            unavailableSources.length === 0
              ? "Oficina e Governance em tempo real."
              : `Fontes indisponíveis: ${unavailableSources.join(", ")}.`
          }
        />

        {/* Task List */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 flex-1 overflow-hidden flex flex-col">
          <div className="overflow-y-auto p-0">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-900 sticky top-0">
                <tr>
                  <th className="px-6 py-4 font-semibold">Tarefa</th>
                  <th className="px-6 py-4 font-semibold">Categoria</th>
                  <th className="px-6 py-4 font-semibold">Origem</th>
                  <th className="px-6 py-4 font-semibold">Estado</th>
                  <th className="px-6 py-4 font-semibold">Criado em</th>
                  <th className="px-6 py-4 font-semibold text-right">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tasks.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                      <div className="flex flex-col items-center gap-2">
                        <CheckCircle2 size={32} className="text-emerald-500 mb-2" />
                        <p className="font-medium text-slate-700">Tudo limpo!</p>
                        <p>Não tem tarefas pendentes de momento.</p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  tasks.map((task) => (
                    <tr key={task.id} className="hover:bg-slate-50 transition-colors group cursor-pointer">
                      <td className="px-6 py-4">
                        <p className="font-medium text-slate-900 line-clamp-1">{task.title}</p>
                        {task.slaDueAt && (
                          <div className="flex items-center gap-1 mt-1 text-xs text-rose-600 font-medium">
                            <AlertCircle size={12} />
                            SLA: {format(new Date(task.slaDueAt), "dd MMM, HH:mm", { locale: ptBR })}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          {task.category.includes("Mecânica") ? <Wrench size={14} className="text-slate-400" /> : <Clock size={14} className="text-slate-400" />}
                          {task.category}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">
                          {task.source}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <StatusBadge status={task.status} />
                      </td>
                      <td className="px-6 py-4 text-slate-500">
                        {format(new Date(task.createdAt), "dd MMM yyyy", { locale: ptBR })}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          href={`/tarefas/${task.id}?source=${task.source}`}
                          className="text-blue font-medium hover:text-blue-dark text-sm opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          Ver detalhes &rarr;
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
