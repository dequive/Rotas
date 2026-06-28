"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Truck, Users, Check, AlertCircle, ArrowRight } from "lucide-react";
import { assignTripOrder, type TripOrder } from "../lib/trip-orders-api";
import type { Vehicle } from "../lib/vehicles-api";
import type { Driver } from "../lib/drivers-api";

interface DispatchBoardProps {
  pendingOrders: TripOrder[];
  vehicles: Vehicle[];
  drivers: Driver[];
}

export function DispatchBoard({ pendingOrders, vehicles, drivers }: DispatchBoardProps) {
  const router = useRouter();
  const [selectedOrder, setSelectedOrder] = useState<TripOrder | null>(null);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>("");
  const [selectedDriverId, setSelectedDriverId] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const availableVehicles = vehicles.filter(v => v.status === "active");
  const availableDrivers = drivers.filter(d => d.status === "active");

  const handleAssign = async () => {
    if (!selectedOrder || !selectedVehicleId || !selectedDriverId) return;
    
    setIsSubmitting(true);
    try {
      await assignTripOrder(selectedOrder.id, selectedVehicleId, selectedDriverId);
      setSelectedOrder(null);
      setSelectedVehicleId("");
      setSelectedDriverId("");
      router.refresh();
    } catch (error) {
      alert("Erro ao despachar viagem. Verifique se o veículo ou motorista estão ocupados.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (pendingOrders.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 text-center flex flex-col items-center justify-center mb-6 mt-4">
        <div className="w-12 h-12 bg-green-50 text-green-600 rounded-full flex items-center justify-center mb-3">
          <Check size={24} />
        </div>
        <h3 className="font-semibold text-slate-800">Tudo Despachado!</h3>
        <p className="text-sm text-slate-500 max-w-sm mt-1">Não existem ordens de viagem pendentes de atribuição neste momento.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-6 mt-4">
      <div className="border-b border-slate-200 p-4 bg-slate-50 flex items-center justify-between">
        <h2 className="font-semibold text-slate-800 flex items-center gap-2">
          <ArrowRight size={18} className="text-blue-600" />
          Quadro de Despacho Operacional
        </h2>
        <span className="text-xs font-semibold px-2 py-1 bg-amber-100 text-amber-800 rounded-md border border-amber-200">
          {pendingOrders.length} Viagens Planeadas
        </span>
      </div>

      <div className="divide-y divide-slate-100">
        {pendingOrders.map((order) => (
          <div key={order.id} className="p-4 hover:bg-slate-50 transition-colors flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                  {order.order_number || order.id.slice(0,8).toUpperCase()}
                </span>
                <span className="font-semibold text-slate-800">{order.customer_name || "Cliente Interno"}</span>
              </div>
              <p className="text-sm text-slate-600">
                <span className="font-medium text-slate-700">{order.origin}</span> → <span className="font-medium text-slate-700">{order.destination}</span>
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Carga: {order.cargo_type || "Geral"} • Peso: {order.cargo_weight_kg || 0} kg
              </p>
            </div>
            
            <button
              onClick={() => setSelectedOrder(order)}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              Atribuir Motorista
            </button>
          </div>
        ))}
      </div>

      {selectedOrder && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full overflow-hidden">
            <div className="p-4 border-b border-slate-100 bg-slate-50">
              <h3 className="font-semibold text-slate-800">Despachar Viagem</h3>
              <p className="text-xs text-slate-500 mt-1">{selectedOrder.origin} → {selectedOrder.destination}</p>
            </div>
            
            <div className="p-6 flex flex-col gap-5">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1 flex items-center gap-2">
                  <Truck size={14} className="text-slate-400" /> Selecionar Viatura
                </label>
                <select 
                  className="w-full border border-slate-300 rounded-lg p-2.5 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  value={selectedVehicleId}
                  onChange={(e) => setSelectedVehicleId(e.target.value)}
                >
                  <option value="">-- Escolha uma viatura livre --</option>
                  {availableVehicles.map(v => (
                    <option key={v.id} value={v.id}>{v.plate} ({v.brand} {v.model})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1 flex items-center gap-2">
                  <Users size={14} className="text-slate-400" /> Selecionar Motorista
                </label>
                <select 
                  className="w-full border border-slate-300 rounded-lg p-2.5 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  value={selectedDriverId}
                  onChange={(e) => setSelectedDriverId(e.target.value)}
                >
                  <option value="">-- Escolha um motorista livre --</option>
                  {availableDrivers.map(d => (
                    <option key={d.id} value={d.id}>{d.full_name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="p-4 border-t border-slate-100 bg-slate-50 flex gap-3 justify-end">
              <button
                onClick={() => setSelectedOrder(null)}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200 rounded-lg transition-colors"
                disabled={isSubmitting}
              >
                Cancelar
              </button>
              <button
                onClick={handleAssign}
                disabled={!selectedVehicleId || !selectedDriverId || isSubmitting}
                className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {isSubmitting ? "A Despachar..." : "Confirmar Despacho"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
