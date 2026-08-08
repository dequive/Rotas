"use client";

import { useEffect, useState } from "react";
import { Loader2, Wrench, Settings } from "lucide-react";
import { bffRequest } from "@/app/lib/bff";

export default function TabWorkshop({ vehicleId }: { vehicleId: string }) {
  const [workOrders, setWorkOrders] = useState<any[]>([]);
  const [parts, setParts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [resWorkOrders, resParts] = await Promise.all([
          bffRequest(`/api/v1/workshop/work-orders?vehicle_id=${vehicleId}&limit=5`),
          bffRequest(`/api/v1/workshop/vehicles/${vehicleId}/installed-parts`)
        ]);
        
        if (resWorkOrders.ok) {
          const wo = await resWorkOrders.json();
          setWorkOrders(wo.items || wo);
        }
        if (resParts.ok) {
          const p = await resParts.json();
          setParts(p.items || p);
        }
      } catch (err) {
        console.error("Failed to load workshop data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [vehicleId]);

  if (loading) {
    return <div className="p-12 flex justify-center"><Loader2 className="animate-spin text-slate-400" size={32} /></div>;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Ordens de Reparação */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Wrench size={20} className="text-amber-600" />
          <h3 className="text-lg font-bold text-slate-900">Histórico de Oficina</h3>
        </div>
        
        {workOrders.length === 0 ? (
          <p className="text-sm text-slate-500 py-4">Sem histórico de manutenção registado.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {workOrders.map((wo: any, idx) => (
              <div key={idx} className="flex justify-between items-center p-3 rounded-xl bg-slate-50 border border-slate-100">
                <div>
                  <p className="text-sm font-bold text-slate-900">{wo.description || "Revisão Geral"}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{wo.started_at ? wo.started_at.slice(0,10) : "Agendada"}</p>
                </div>
                <span className={`px-2.5 py-1 text-[11px] font-bold uppercase rounded-md ${
                  wo.status === "completed" ? "bg-slate-200 text-slate-700" :
                  "bg-amber-100 text-amber-700"
                }`}>
                  {wo.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Peças Instaladas */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Settings size={20} className="text-indigo-600" />
          <h3 className="text-lg font-bold text-slate-900">Peças e Pneus</h3>
        </div>

        {parts.length === 0 ? (
          <p className="text-sm text-slate-500 py-4">Nenhuma peça ou componente rastreado.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {parts.map((part: any, idx) => (
              <div key={idx} className="flex justify-between items-center p-3 rounded-xl bg-slate-50 border border-slate-100">
                <div className="flex flex-col">
                  <p className="text-sm font-bold text-slate-900">{part.part_name || "Peça não identificada"}</p>
                  <p className="text-xs text-slate-500 mt-0.5">SN: {part.serial_number || "N/A"}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-bold text-slate-900">{part.installed_at ? part.installed_at.slice(0,10) : "Desconhecido"}</p>
                  <p className="text-[10px] text-slate-500">Data de instalação</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
