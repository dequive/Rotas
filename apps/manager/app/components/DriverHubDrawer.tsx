"use client";

import { useEffect, useState } from "react";
import { X, AlertTriangle, AlertCircle, MapPin, DollarSign } from "lucide-react";
import { loadDriverHub360 } from "../lib/drivers-client-api";
import type { DriverHub360Response } from "../lib/drivers-api";

export function DriverHubDrawer({
  driverId,
  open,
  onClose,
}: {
  driverId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const [data, setData] = useState<DriverHub360Response | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && driverId) {
      setLoading(true);
      loadDriverHub360(driverId)
        .then(setData)
        .finally(() => setLoading(false));
    } else {
      setData(null);
    }
  }, [open, driverId]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/40 z-40 transition-opacity" 
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 w-full max-w-md bg-surface border-l border-border shadow-xl z-50 flex flex-col transform transition-transform duration-300">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold">Hub 360 do Motorista</h2>
          <button onClick={onClose} className="p-2 hover:bg-muted rounded-full">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="text-center text-muted py-8 animate-pulse">A carregar raio-x do motorista...</div>
          ) : data ? (
            <>
              {/* Perfil */}
              <div>
                <h3 className="text-xl font-bold">{data.driver.full_name}</h3>
                <p className="text-sm text-muted">{data.driver.phone}</p>
              </div>

              {/* Alertas */}
              {data.document_alerts.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-muted uppercase tracking-wider">Alertas Documentais</h4>
                  <div className="flex flex-col gap-2">
                    {data.document_alerts.map((alert, i) => (
                      <div key={i} className={`flex items-start gap-3 p-3 rounded-md border ${alert.status === 'expired' ? 'bg-red-50/50 border-red-200 text-red-800' : 'bg-orange-50/50 border-orange-200 text-orange-800'}`}>
                        {alert.status === 'expired' ? <AlertCircle size={18} className="mt-0.5" /> : <AlertTriangle size={18} className="mt-0.5" />}
                        <span className="text-sm">{alert.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tesouraria */}
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-muted uppercase tracking-wider">Tesouraria (Adiantamentos)</h4>
                <div className="bg-blue-50/50 border border-blue-100 rounded-md p-4 flex items-center gap-4">
                  <div className="p-3 bg-blue-100 rounded-full text-blue-700">
                    <DollarSign size={24} />
                  </div>
                  <div>
                    <p className="text-sm text-blue-900/70">Aguardando Acerto de Contas</p>
                    <p className="text-2xl font-bold text-blue-900">
                      {Number(data.pending_advances_total).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                    </p>
                    <p className="text-xs text-blue-800/60 mt-1">
                      {data.pending_advances_count} adiantamento(s) em aberto
                    </p>
                  </div>
                </div>
              </div>

              {/* Viagens */}
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-muted uppercase tracking-wider">Últimas Viagens</h4>
                {data.recent_trips.length === 0 ? (
                  <p className="text-sm text-muted">Sem viagens registadas recentemente.</p>
                ) : (
                  <div className="border border-border rounded-md divide-y divide-border">
                    {data.recent_trips.map(trip => (
                      <div key={trip.id} className="p-3 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <MapPin size={16} className="text-muted" />
                          <span className="text-sm font-medium">{trip.route_name || 'Rota N/D'}</span>
                        </div>
                        <span className="text-xs px-2 py-1 bg-muted rounded-full uppercase tracking-wider">
                          {trip.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="text-center text-muted py-8">Erro ao carregar dados.</div>
          )}
        </div>
      </div>
    </>
  );
}
