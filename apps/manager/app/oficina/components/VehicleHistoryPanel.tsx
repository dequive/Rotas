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
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"receptions" | "work_orders" | "parts" | "warranties">("receptions");

  useEffect(() => {
    if (!vehicleId) {
      setHistory(null);
      setError(null);
      return;
    }

    async function fetchHistory() {
      setIsLoading(true);
      setError(null);
      setHistory(null);
      try {
        const res = await bffRequest(
          `/api/v1/workshop/receptions/vehicles/${vehicleId}/history`,
        );
        if (res.ok) {
          const data = await res.json();
          setHistory(data);
        } else {
          const body = (await res.json().catch(() => ({}))) as {
            detail?: string;
            error?: { message?: string };
          };
          setError(
            body.error?.message ??
              body.detail ??
              `Não foi possível carregar o histórico (HTTP ${res.status}).`,
          );
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Erro de ligação ao carregar o histórico.",
        );
      } finally {
        setIsLoading(false);
      }
    }

    fetchHistory();
  }, [vehicleId]);

  if (!vehicleId) {
    return (
      <div className="rounded-lg border border-border bg-surface-2 p-5 text-center text-xs text-muted">
        Selecione uma viatura para visualizar o histórico de intervenções anteriores.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-5 text-xs text-muted">
        <h4 className="mb-3 text-sm font-bold text-ink">Histórico de Intervenções</h4>
        <p className="text-center animate-pulse">A carregar histórico da viatura...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-status-cancelled bg-status-cancelled-soft p-4 text-sm text-status-cancelled"
      >
        <h4 className="font-semibold">Histórico indisponível</h4>
        <p className="mt-1 text-xs">{error}</p>
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
    <div className="space-y-3 rounded-lg border border-border bg-surface p-4 shadow-card">
      <div className="flex items-center justify-between border-b border-border pb-2">
        <div>
          <h4 className="text-sm font-bold text-ink">Histórico de Intervenções</h4>
          <p className="text-[11px] text-muted">
            Viatura: <span className="font-semibold text-ink">{history?.plate || "N/D"}</span> | Odómetro
            histórico: <span className="font-mono font-semibold tabular-nums text-ink">{history?.current_odometer_km || 0} km</span>
          </p>
        </div>
        {history?.warranties && history.warranties.filter((w) => w.status === "active").length > 0 && (
          <span className="rounded-full border border-status-awaiting bg-status-awaiting-soft px-2 py-0.5 text-[10px] font-semibold text-status-awaiting">
            Garantia ativa
          </span>
        )}
      </div>

      {isEmpty ? (
        <div className="rounded border border-dashed border-border bg-surface-2 py-4 text-center text-xs text-muted">
          Primeira entrada desta viatura na oficina. Sem registos anteriores.
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
