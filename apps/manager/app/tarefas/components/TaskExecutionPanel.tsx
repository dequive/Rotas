"use client";

import { useState } from "react";
import { Wrench, DollarSign, PenTool, User, AlertCircle, Plus } from "lucide-react";
import { ExternalCostModal } from "./ExternalCostModal";

export function TaskExecutionPanel({ taskId, source, initialWorkOrder = null }: { taskId: string, source: string, initialWorkOrder?: any }) {
  const [workOrder, setWorkOrder] = useState(initialWorkOrder);
  const [isCostModalOpen, setIsCostModalOpen] = useState(false);

  if (!workOrder) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col items-center justify-center text-center gap-4 py-12 mt-6">
        <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center border border-slate-100">
          <Wrench size={24} className="text-slate-400" />
        </div>
        <div>
          <h3 className="font-semibold text-slate-800">Sem Ordem de Execução</h3>
          <p className="text-sm text-slate-500 mt-1 max-w-sm">
            Esta tarefa ainda não tem uma ordem de serviço associada para rastreio de custos, ferramentas e técnicos externos.
          </p>
        </div>
        <button 
          className="mt-2 flex items-center gap-2 bg-slate-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors"
          onClick={() => alert("Em breve: Abre modal para criar a Ordem de Serviço")}
        >
          <Plus size={16} />
          Iniciar Execução
        </button>
      </div>
    );
  }

  // Se já existir uma ordem de serviço
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mt-6">
      <div className="border-b border-slate-200 p-4 bg-slate-50 flex items-center justify-between">
        <h2 className="font-semibold text-slate-800 flex items-center gap-2">
          <Wrench size={18} className="text-slate-500" />
          Painel de Execução & Custos
        </h2>
        <span className="text-xs font-semibold px-2 py-1 bg-green-100 text-green-700 rounded-md border border-green-200">
          OS: {workOrder.work_order_number || "Em Progresso"}
        </span>
      </div>

      <div className="p-6">
        <div className="grid grid-cols-2 gap-6 mb-6">
          <div className="border border-slate-200 rounded-xl p-4 flex items-start gap-4">
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <DollarSign size={20} />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Custo Total Atual</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">
                {workOrder.actual_cost ? `${workOrder.actual_cost} MZN` : "0.00 MZN"}
              </p>
              <p className="text-xs text-slate-400 mt-1">Estimado: {workOrder.estimated_cost || "0.00"} MZN</p>
            </div>
          </div>

          <div className="border border-slate-200 rounded-xl p-4 flex items-start gap-4">
            <div className="p-2 bg-orange-50 text-orange-600 rounded-lg">
              <User size={20} />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Técnico / Fornecedor</p>
              <p className="text-sm font-semibold text-slate-900 mt-1">
                {workOrder.service_provider_third_party_id ? "Entidade Externa (via Terceiros)" : "Técnico Interno"}
              </p>
              <p className="text-xs text-slate-400 mt-1">Mão de obra: {workOrder.labor_cost || "0.00"} MZN</p>
            </div>
          </div>
        </div>

        <div className="flex gap-3">
          <button className="flex-1 py-2 border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 flex items-center justify-center gap-2 transition-colors">
            <PenTool size={16} /> Adicionar Material
          </button>
          <button className="flex-1 py-2 border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 flex items-center justify-center gap-2 transition-colors">
            <User size={16} /> Atribuir Externo
          </button>
          <button 
            onClick={() => setIsCostModalOpen(true)}
            className="flex-1 py-2 border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 flex items-center justify-center gap-2 transition-colors"
          >
            <DollarSign size={16} /> Registar Custo (Fatura)
          </button>
        </div>
      </div>
      
      <ExternalCostModal 
        isOpen={isCostModalOpen} 
        onClose={() => setIsCostModalOpen(false)} 
        workOrderId={workOrder.id} 
      />
    </div>
  );
}
