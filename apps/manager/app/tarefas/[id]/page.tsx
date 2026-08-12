import { SidebarLayout } from "@/app/components/SidebarLayout";
import { ArrowLeft, MessageSquare, CheckCircle, Clock, FileText, User } from "lucide-react";
import Link from "next/link";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { apiFetch } from "@/app/lib/api";
import { requireSession } from "@/app/lib/auth";
import { TaskActions } from "../components/TaskActions";
import { TaskNotes } from "../components/TaskNotes";
import { TaskExecutionPanel } from "../components/TaskExecutionPanel";
export const dynamic = "force-dynamic";

async function getTaskDetails(id: string, source: string) {
  if (source === "workshop") {
    const [data, notesData] = await Promise.all([
      apiFetch<any>(`/api/v1/workshop/maintenance-requests/${id}`).catch(() => null),
      apiFetch<any[]>(`/api/v1/workshop/maintenance-requests/${id}/notes`).catch(() => [])
    ]);
    
    if (!data) return null;
    return {
      id: data.id,
      title: data.description || "Pedido de Manutenção",
      status: data.status,
      createdAt: data.created_at,
      details: data,
      source: "workshop",
      category: "Mecânica/Frota",
      notes: notesData || [],
    };
  } else {
    // Governance case
    const session = await requireSession();
    const GOVERNANCE_API = process.env.GOVERNANCE_API_URL || "http://localhost:8001";
    
    const [caseRes, notesRes] = await Promise.all([
      fetch(`${GOVERNANCE_API}/api/v1/cases/${id}`, {
        headers: { "Authorization": `Bearer ${session.accessToken}`, "X-Tenant-Id": session.tenantId }
      }).catch(() => null),
      fetch(`${GOVERNANCE_API}/api/v1/cases/${id}/notes`, {
        headers: { "Authorization": `Bearer ${session.accessToken}`, "X-Tenant-Id": session.tenantId }
      }).catch(() => null)
    ]);

    const caseData = caseRes && caseRes.ok ? await caseRes.json() : null;
    const notesData = notesRes && notesRes.ok ? await notesRes.json() : [];

    if (!caseData) return null;

    return {
      id: caseData.id,
      title: caseData.title || "Caso Interno",
      status: caseData.status,
      createdAt: caseData.created_at,
      details: caseData,
      source: "governance",
      category: "Back-office",
      notes: notesData,
    };
  }
}

export default async function TarefaDetailsPage({ params, searchParams }: { params: Promise<{ id: string }>, searchParams: Promise<{ source: string }> }) {
  const [{ id }, { source }] = await Promise.all([params, searchParams]);
  const task = await getTaskDetails(id, source);

  if (!task) {
    return (
      <SidebarLayout active="tarefas">
        <div className="p-6">
          <p>Tarefa não encontrada.</p>
        </div>
      </SidebarLayout>
    );
  }

  return (
    <SidebarLayout active="tarefas">
      <div className="p-6 max-w-5xl mx-auto flex flex-col gap-6 h-full">
        {/* Header */}
        <div className="flex items-center gap-4 border-b border-slate-200 pb-4">
          <Link href="/tarefas" className="p-2 hover:bg-slate-100 rounded-full transition-colors">
            <ArrowLeft size={20} className="text-slate-600" />
          </Link>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-slate-900">{task.title}</h1>
            <div className="flex gap-4 mt-2 text-sm text-slate-500">
              <span className="flex items-center gap-1"><Clock size={14} /> {format(new Date(task.createdAt), "dd MMM yyyy, HH:mm", { locale: ptBR })}</span>
              <span className="flex items-center gap-1"><FileText size={14} /> Ref: {task.id.split("-")[0]}</span>
              <span className="uppercase tracking-wider font-semibold opacity-70 border-l pl-4 border-slate-300">{task.source}</span>
            </div>
          </div>
          
          <div className="flex flex-col items-end">
            <span className="px-3 py-1.5 bg-blue-100 text-blue-800 rounded-lg text-sm font-semibold border border-blue-200 uppercase tracking-wide">
              {task.status}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-6">
          {/* Main Content Area */}
          <div className="col-span-2 flex flex-col gap-6">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
                <FileText size={18} className="text-indigo-600" /> Detalhes do Pedido
              </h2>
              <div className="prose prose-sm prose-slate max-w-none text-slate-700">
                <p>{task.details.description || "Nenhuma descrição fornecida."}</p>
              </div>
            </div>

            {/* Notes / Activities */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
                <MessageSquare size={18} className="text-indigo-600" /> Histórico e Notas
              </h2>
              
              <div className="flex flex-col gap-4">
                {task.notes && task.notes.length > 0 ? (
                  task.notes.map((note: any) => (
                    <div key={note.id} className="flex gap-4 p-4 rounded-lg bg-slate-50 border border-slate-100">
                      <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center flex-shrink-0 font-bold text-sm">
                        <User size={14} />
                      </div>
                      <div>
                        <div className="flex items-baseline gap-2 mb-1">
                          <span className="font-semibold text-slate-800">Utilizador</span>
                          <span className="text-xs text-slate-400">{format(new Date(note.created_at), "dd MMM, HH:mm", { locale: ptBR })}</span>
                        </div>
                        <p className="text-sm text-slate-600">{note.body}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500 italic">Sem histórico de anotações.</p>
                )}

                <TaskNotes taskId={task.id} source={task.source as "workshop" | "governance"} />
              </div>
            </div>

            <TaskExecutionPanel taskId={task.id} source={task.source as "workshop" | "governance"} />
          </div>

          {/* Sidebar Area */}
          <div className="col-span-1 flex flex-col gap-6">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h2 className="text-sm font-semibold text-slate-800 mb-4 uppercase tracking-wider">Ações Rápidas</h2>
              <TaskActions taskId={task.id} source={task.source as "workshop" | "governance"} currentStatus={task.status} />
            </div>

            <div className="bg-slate-50 rounded-xl border border-slate-200 p-6">
              <h2 className="text-sm font-semibold text-slate-800 mb-4 uppercase tracking-wider">Metadados</h2>
              <div className="flex flex-col gap-3 text-sm">
                <div className="flex justify-between border-b border-slate-200 pb-2">
                  <span className="text-slate-500">Categoria</span>
                  <span className="font-medium text-slate-800">{task.category}</span>
                </div>
                <div className="flex justify-between border-b border-slate-200 pb-2">
                  <span className="text-slate-500">Origem de Dados</span>
                  <span className="font-medium text-slate-800 uppercase text-xs mt-0.5">{task.source}</span>
                </div>
                {task.details.sla_due_at && (
                  <div className="flex justify-between pb-2">
                    <span className="text-slate-500">Prazo (SLA)</span>
                    <span className="font-medium text-rose-600">{format(new Date(task.details.sla_due_at), "dd MMM, HH:mm", { locale: ptBR })}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
