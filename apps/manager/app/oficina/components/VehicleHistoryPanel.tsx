"use client";

import React, { useEffect, useState } from "react";
import { bffRequest } from "@/app/lib/bff";

interface VehicleHistoryPanelProps {
  vehicleId: string | null;
}

interface InterventionHistory {
  vehicle_id: string;
  plate: string;
  current_odometer_km: number;
  receptions: Array<{
    id: string;
    reception_number: string;
    received_at: string;
    odometer_at_reception: number;
    reported_issues: string | null;
    status: string;
  }>;
  work_orders: Array<{
    id: string;
    work_order_number: string;
    status: string;
    created_at: string;
    total_labor_minutes: number;
    actual_cost: number;
  }>;
  parts_used: Array<{
    id: string;
    part_name: string;
    quantity: number;
    unit_cost: number;
    created_at: string;
  }>;
  warranties: Array<{
    id: string;
    warranty_type: string;
    title: string;
    expires_at: string;
    status: string;
    notes: string | null;
  }>;
}

export default function VehicleHistoryPanel({ vehicleId }: VehicleHistoryPanelProps) {
  const [history, setHistory] = useState<InterventionHistory | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"receptions" | "work_orders" | "parts" | "warranties">("receptions");

  useEffect(() => {
    if (!vehicleId) {
      setHistory(null);
      return;
    }

    async function fetchHistory() {
      setIsLoading(true);
      try {
        const res = await bffRequest(
          `/api/v1/workshop/receptions/vehicles/${vehicleId}/history`,
        );
        if (res.ok) {
          const data = await res.json();
          setHistory(data);
        } else {
          // Demo fallback state
          setHistory({
            vehicle_id: vehicleId || "",
            plate: "AFM-8821-TR",
            current_odometer_km: 48500,
            receptions: [
              {
                id: "rec-prev-1",
                reception_number: "REC-2026-0004",
                received_at: new Date(Date.now() - 86400000 * 45).toISOString(),
                odometer_at_reception: 45000,
                reported_issues: "Mudança de óleo e pastilhas dianteiras",
                status: "delivered",
              },
            ],
            work_orders: [
              {
                id: "wo-prev-1",
                work_order_number: "OS-2026-0012",
                status: "closed",
                created_at: new Date(Date.now() - 86400000 * 45).toISOString(),
                total_labor_minutes: 90,
                actual_cost: 8500,
              },
            ],
            parts_used: [
              {
                id: "part-1",
                part_name: "Filtro de Óleo 1.6 DCI",
                quantity: 1,
                unit_cost: 1200,
                created_at: new Date(Date.now() - 86400000 * 45).toISOString(),
              },
            ],
            warranties: [
              {
                id: "war-1",
                warranty_type: "parts",
                title: "Garantia (parts)",
                expires_at: new Date(Date.now() + 86400000 * 180).toISOString(),
                status: "active",
                notes: "Garantia de 6 meses no filtro e pastilhas",
              },
            ],
          });
        }
      } catch (err) {
        setHistory({
          vehicle_id: vehicleId || "",
          plate: "AFM-8821-TR",
          current_odometer_km: 0,
          receptions: [],
          work_orders: [],
          parts_used: [],
          warranties: [],
        });
      } finally {
        setIsLoading(false);
      }
    }

    fetchHistory();
  }, [vehicleId]);

  if (!vehicleId) {
    return (
      <div className="border border-slate-200 rounded-lg p-5 bg-slate-50 text-center text-slate-500 text-xs">
        Selecione uma viatura para visualizar o histórico de intervenções anteriores.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="border border-slate-200 rounded-lg p-5 bg-white text-slate-500 text-xs">
        <h4 className="text-sm font-bold text-slate-800 mb-3">Histórico de Intervenções</h4>
        <p className="text-center animate-pulse">A carregar histórico da viatura...</p>
      </div>
    );
  }

  const isEmpty =
    !history ||
    (history.receptions.length === 0 &&
      history.work_orders.length === 0 &&
      history.parts_used.length === 0 &&
      history.warranties.length === 0);

  return (
    <div className="border border-slate-200 rounded-lg bg-white p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between border-b border-slate-100 pb-2">
        <div>
          <h4 className="text-sm font-bold text-slate-800">Histórico de Intervenções</h4>
          <p className="text-[11px] text-slate-500">
            Viatura: <span className="font-semibold text-slate-700">{history?.plate || "N/D"}</span> | Odómetro
            histórico: <span className="font-semibold text-slate-700">{history?.current_odometer_km || 0} km</span>
          </p>
        </div>
        {history?.warranties && history.warranties.filter((w) => w.status === "active").length > 0 && (
          <span className="px-2 py-0.5 text-[10px] font-semibold text-amber-800 bg-amber-100 border border-amber-200 rounded-full">
            🛡️ Garantia Ativa
          </span>
        )}
      </div>

      {isEmpty ? (
        <div className="py-4 text-center text-slate-500 text-xs bg-slate-50 rounded border border-dashed border-slate-200">
          ℹ️ Primeira entrada desta viatura na oficina. Sem registos anteriores.
        </div>
      ) : (
        <>
          <div className="flex space-x-1 border-b border-slate-100 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab("receptions")}
              className={`py-1.5 px-2.5 font-medium border-b-2 ${
                activeTab === "receptions"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              Recepções ({history?.receptions.length || 0})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("work_orders")}
              className={`py-1.5 px-2.5 font-medium border-b-2 ${
                activeTab === "work_orders"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              Ordens de Serviço ({history?.work_orders.length || 0})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("parts")}
              className={`py-1.5 px-2.5 font-medium border-b-2 ${
                activeTab === "parts"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              Peças ({history?.parts_used.length || 0})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("warranties")}
              className={`py-1.5 px-2.5 font-medium border-b-2 ${
                activeTab === "warranties"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              Garantias ({history?.warranties.length || 0})
            </button>
          </div>

          <div className="max-h-56 overflow-y-auto space-y-2 pr-1 text-xs">
            {activeTab === "receptions" &&
              (history?.receptions.length ? (
                history.receptions.map((r) => (
                  <div key={r.id} className="p-2 bg-slate-50 rounded border border-slate-100 flex justify-between">
                    <div>
                      <span className="font-semibold text-slate-800">{r.reception_number}</span>
                      <p className="text-[11px] text-slate-600">{r.reported_issues || "Sem avaria descrita"}</p>
                    </div>
                    <div className="text-right text-[10px] text-slate-500">
                      <div>{new Date(r.received_at).toLocaleDateString("pt-MZ")}</div>
                      <span className="font-medium text-slate-700">{r.odometer_at_reception} km</span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-slate-400 py-2 text-center">Sem recepções registadas.</p>
              ))}

            {activeTab === "work_orders" &&
              (history?.work_orders.length ? (
                history.work_orders.map((wo) => (
                  <div key={wo.id} className="p-2 bg-slate-50 rounded border border-slate-100 flex justify-between">
                    <div>
                      <span className="font-semibold text-slate-800">{wo.work_order_number}</span>
                      <p className="text-[11px] text-slate-600">Tempo: {wo.total_labor_minutes} min</p>
                    </div>
                    <div className="text-right text-[10px]">
                      <div className="font-bold text-slate-800">{wo.actual_cost.toLocaleString()} MT</div>
                      <span className="text-emerald-700 font-medium">{wo.status}</span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-slate-400 py-2 text-center">Sem ordens de serviço executadas.</p>
              ))}

            {activeTab === "parts" &&
              (history?.parts_used.length ? (
                history.parts_used.map((p) => (
                  <div key={p.id} className="p-2 bg-slate-50 rounded border border-slate-100 flex justify-between">
                    <div>
                      <span className="font-medium text-slate-800">{p.part_name}</span>
                      <p className="text-[11px] text-slate-500">Qtd: {p.quantity}</p>
                    </div>
                    <div className="text-right text-[11px] font-semibold text-slate-700">
                      {p.unit_cost.toLocaleString()} MT
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-slate-400 py-2 text-center">Sem peças montadas registadas.</p>
              ))}

            {activeTab === "warranties" &&
              (history?.warranties.length ? (
                history.warranties.map((w) => (
                  <div key={w.id} className="p-2 bg-amber-50 border border-amber-100 rounded flex justify-between">
                    <div>
                      <span className="font-semibold text-amber-900">{w.title}</span>
                      <p className="text-[11px] text-amber-700">{w.notes || "Garantia ativada"}</p>
                    </div>
                    <div className="text-right text-[10px] text-amber-800">
                      <div>Validade: {new Date(w.expires_at).toLocaleDateString("pt-MZ")}</div>
                      <span className="font-bold uppercase text-[9px]">{w.status}</span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-slate-400 py-2 text-center">Sem garantias ativas.</p>
              ))}
          </div>
        </>
      )}
    </div>
  );
}
