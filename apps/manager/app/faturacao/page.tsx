import { Suspense } from "react";
import { FileText, CheckCircle, Clock, AlertCircle, FilePlus, DollarSign } from "lucide-react";
import { StatCard } from "@/app/components/ui/StatCard";
import { FaturacaoClient } from "./FaturacaoClient";

export default function FaturacaoPage() {
  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-ink">Faturação de Transportes</h1>
          <p className="text-muted">Apuramento de Guias (POD) e Emissão de Faturas Oficiais.</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors">
          <FilePlus size={18} /> Criar Fatura Manual
        </button>
      </div>

      {/* KPIs Faturação */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title="Guias Prontas (Billable)"
          value="142"
          change="+12"
          changeType="positive"
          icon={<CheckCircle className="text-blue-500" size={24} />}
        />
        <StatCard
          title="Faturado este Mês"
          value="12.4M MZN"
          change="+5%"
          changeType="positive"
          icon={<DollarSign className="text-emerald-500" size={24} />}
        />
        <StatCard
          title="Faturas em Atraso"
          value="3"
          change="Ação necessária"
          changeType="negative"
          icon={<AlertCircle className="text-red-500" size={24} />}
        />
        <StatCard
          title="Aguardando POD"
          value="45 Viagens"
          change="-2"
          changeType="positive"
          icon={<Clock className="text-orange-500" size={24} />}
        />
      </div>

      <div className="bg-surface border border-border rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-border bg-surface-2 flex justify-between items-center">
          <h2 className="font-semibold text-lg text-ink flex items-center gap-2">
            <FileText size={20} className="text-blue-500" />
            Emissão em Lote por Cliente
          </h2>
          <span className="text-sm text-muted">Apenas clientes com viagens "Billable"</span>
        </div>

        <div className="p-6">
          <Suspense fallback={<div className="animate-pulse h-32 bg-surface-2 rounded-lg" />}>
            <FaturacaoClient />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
