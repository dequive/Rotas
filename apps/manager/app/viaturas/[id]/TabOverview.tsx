"use client";

import { useEffect, useState } from "react";
import { Loader2, MapPin, CheckSquare, AlertTriangle } from "lucide-react";
import { bffRequest } from "@/app/lib/bff";

export default function TabOverview({ vehicleId }: { vehicleId: string }) {
  const [trips, setTrips] = useState<any[]>([]);
  const [checklists, setChecklists] = useState<any[]>([]);
  const [tripsError, setTripsError] = useState(false);
  const [checklistsError, setChecklistsError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [resTrips, resChecklists] = await Promise.all([
          bffRequest(`/api/v1/trips?vehicle_id=${vehicleId}&limit=5`),
          bffRequest(`/api/v1/checklists?vehicle_id=${vehicleId}&limit=5`)
        ]);
        
        if (resTrips.ok) {
          const t = await resTrips.json();
          setTrips(t.items || t);
        } else {
          setTripsError(true);
        }
        if (resChecklists.ok) {
          const c = await resChecklists.json();
          setChecklists(c.items || c);
        } else {
          setChecklistsError(true);
        }
      } catch (err) {
        console.error("Failed to load overview data", err);
        setTripsError(true);
        setChecklistsError(true);
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
      {/* Viagens Recentes */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <MapPin size={20} className="text-indigo-600" />
          <h3 className="text-lg font-bold text-slate-900">Viagens Recentes</h3>
        </div>
        
        {tripsError ? (
          <p role="alert" className="rounded-r-md border border-error-border bg-error-bg p-3 text-sm text-error">
            Não foi possível carregar as viagens recentes.
          </p>
        ) : trips.length === 0 ? (
          <p className="text-sm text-slate-500 py-4">Nenhum registo de viagem encontrado.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {trips.map((trip: any, idx) => (
              <div key={idx} className="flex justify-between items-center p-3 rounded-xl bg-slate-50 border border-slate-100">
                <div>
                  <p className="text-sm font-bold text-slate-900">{trip.route_name || "Rota não especificada"}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{trip.start_date ? trip.start_date.slice(0,10) : "Data desconhecida"}</p>
                </div>
                <span className={`px-2.5 py-1 text-[11px] font-bold uppercase rounded-md ${
                  trip.status === "completed" ? "bg-emerald-100 text-emerald-700" :
                  trip.status === "in_progress" ? "bg-blue-100 text-blue-700" : "bg-slate-200 text-slate-700"
                }`}>
                  {trip.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Checklists Diárias */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <CheckSquare size={20} className="text-indigo-600" />
          <h3 className="text-lg font-bold text-slate-900">Checklists de Inspeção</h3>
        </div>

        {checklistsError ? (
          <p role="alert" className="rounded-r-md border border-error-border bg-error-bg p-3 text-sm text-error">
            Não foi possível carregar as checklists.
          </p>
        ) : checklists.length === 0 ? (
          <p className="text-sm text-slate-500 py-4">Nenhuma checklist registada.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {checklists.map((check: any, idx) => (
              <div key={idx} className="flex justify-between items-center p-3 rounded-xl bg-slate-50 border border-slate-100">
                <div className="flex flex-col">
                  <p className="text-sm font-bold text-slate-900">Inspeção #{check.id.slice(0,6)}</p>
                  <p className="text-xs text-slate-500 mt-0.5">Criada em: {check.created_at ? check.created_at.slice(0,10) : "N/A"}</p>
                </div>
                {check.has_issues ? (
                  <div className="flex items-center gap-1 text-rose-600 bg-rose-50 px-2 py-1 rounded-md text-xs font-bold">
                    <AlertTriangle size={14} /> Anomalias
                  </div>
                ) : (
                  <div className="text-emerald-600 bg-emerald-50 px-2 py-1 rounded-md text-xs font-bold">
                    Ok
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
