"use client";

import { useEffect, useState } from "react";
import { Loader2, Truck, Package, CheckCircle, FileText, ArrowRight } from "lucide-react";
import { loadTrips, startTrip, completeTrip, closeTrip, dispatchTrip } from "../lib/trips-client-api";
import type { Trip } from "../lib/trips-api";

export function ControlTowerClient() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    const data = await loadTrips();
    setTrips(data);
    setLoading(false);
  }

  async function handleStart(id: string) {
    await startTrip(id);
    await fetchData();
  }

  async function handleComplete(id: string) {
    const km = prompt("Qual a quilometragem de chegada?");
    if (!km) return;
    await completeTrip(id, { km_end: parseFloat(km) });
    await fetchData();
  }

  async function handleClose(id: string) {
    const confirmed = confirm("Confirma a recepção da Guia de Transporte assinada (POD)?");
    if (!confirmed) return;
    await closeTrip(id, { pod_received: true, pod_waiver: false });
    await fetchData();
  }

  const plannedTrips = trips.filter(t => t.status === "planned" || t.status === "dispatched");
  const inProgressTrips = trips.filter(t => t.status === "in_progress");
  const completedTrips = trips.filter(t => t.status === "completed" && t.billing_status !== "billable");
  const billableTrips = trips.filter(t => t.billing_status === "billable" || t.status === "closed");

  function TripCard({ trip, actionLabel, onAction }: { trip: Trip, actionLabel?: string, onAction?: () => void }) {
    return (
      <div className="bg-surface border border-border rounded-lg p-3 shadow-sm flex flex-col gap-2">
        <div className="flex justify-between items-center">
          <span className="font-mono text-xs text-muted">#{trip.id.substring(0,6)}</span>
          <span className="text-[10px] uppercase font-bold px-2 py-1 bg-surface-2 rounded-full">{trip.status}</span>
        </div>
        <div className="text-sm font-semibold text-ink flex items-center gap-1">
          {trip.origin} <ArrowRight size={14} className="text-muted" /> {trip.destination}
        </div>
        <div className="text-xs text-muted flex flex-col gap-1">
          <div className="flex items-center gap-1"><Truck size={12}/> {trip.vehicle_plate || "Sem Viatura"}</div>
          <div className="flex items-center gap-1"><Package size={12}/> {trip.driver_name || "Sem Motorista"}</div>
        </div>
        {onAction && (
          <button 
            onClick={onAction}
            className="mt-2 text-xs w-full py-1.5 bg-blue-50 text-blue-700 font-semibold rounded hover:bg-blue-100 transition-colors"
          >
            {actionLabel}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {loading ? (
        <div className="flex justify-center p-12"><Loader2 className="animate-spin text-muted" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-start">
          
          {/* Coluna 1: Planeadas */}
          <div className="flex flex-col gap-3 p-3 bg-surface-2 rounded-xl min-h-[500px] border border-border">
            <h3 className="font-bold text-ink uppercase tracking-wider text-xs mb-2 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-500"></span>
              Agendadas ({plannedTrips.length})
            </h3>
            {plannedTrips.map(t => (
              <TripCard 
                key={t.id} 
                trip={t} 
                actionLabel="Iniciar Viagem" 
                onAction={() => handleStart(t.id)} 
              />
            ))}
          </div>

          {/* Coluna 2: Em Trânsito */}
          <div className="flex flex-col gap-3 p-3 bg-surface-2 rounded-xl min-h-[500px] border border-border">
            <h3 className="font-bold text-ink uppercase tracking-wider text-xs mb-2 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span>
              Em Trânsito ({inProgressTrips.length})
            </h3>
            {inProgressTrips.map(t => (
              <TripCard 
                key={t.id} 
                trip={t} 
                actionLabel="Marcar como Entregue" 
                onAction={() => handleComplete(t.id)} 
              />
            ))}
          </div>

          {/* Coluna 3: Entregues (Aguarda POD) */}
          <div className="flex flex-col gap-3 p-3 bg-surface-2 rounded-xl min-h-[500px] border border-border">
            <h3 className="font-bold text-ink uppercase tracking-wider text-xs mb-2 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-purple-500"></span>
              Aguardam POD ({completedTrips.length})
            </h3>
            {completedTrips.map(t => (
              <TripCard 
                key={t.id} 
                trip={t} 
                actionLabel="Validar POD (Fechar)" 
                onAction={() => handleClose(t.id)} 
              />
            ))}
          </div>

          {/* Coluna 4: Prontas a Faturar */}
          <div className="flex flex-col gap-3 p-3 bg-surface-2 rounded-xl min-h-[500px] border border-border">
            <h3 className="font-bold text-ink uppercase tracking-wider text-xs mb-2 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              Prontas a Faturar ({billableTrips.length})
            </h3>
            {billableTrips.map(t => (
              <TripCard key={t.id} trip={t} />
            ))}
          </div>

        </div>
      )}
    </div>
  );
}
