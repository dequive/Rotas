"use client";

import { useEffect, useState, useMemo } from "react";
import { loadBillingTrips, createBillingDocument, BillingTrip } from "@/app/lib/billing-api";
import { Calculator, Truck, Loader2, Calendar, CheckSquare, Square, Filter } from "lucide-react";

export function FaturacaoClient() {
  const [trips, setTrips] = useState<BillingTrip[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingClient, setProcessingClient] = useState<string | null>(null);

  // Filtros
  const [periodStart, setPeriodStart] = useState<string>("");
  const [periodEnd, setPeriodEnd] = useState<string>("");

  // Seleção (guarda os IDs das viagens selecionadas)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadTrips();
  }, [periodStart, periodEnd]);

  const loadTrips = async () => {
    setLoading(true);
    try {
      const result = await loadBillingTrips();
      setTrips(result.trips);
      // Por defeito, selecionamos todas as viagens que aparecem
      setSelectedIds(new Set(result.trips.map(t => t.id)));
    } catch (error) {
      console.error("Failed to load billable trips", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleSelection = (tripId: string) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(tripId)) {
      newSet.delete(tripId);
    } else {
      newSet.add(tripId);
    }
    setSelectedIds(newSet);
  };

  const toggleClientSelection = (clientTrips: BillingTrip[], isAllSelected: boolean) => {
    const newSet = new Set(selectedIds);
    clientTrips.forEach(t => {
      if (isAllSelected) newSet.delete(t.id);
      else newSet.add(t.id);
    });
    setSelectedIds(newSet);
  };

  const handleCreateDocument = async (clientName: string, clientTrips: BillingTrip[]) => {
    // Filtrar apenas as selecionadas
    const tripsToBill = clientTrips.filter(t => selectedIds.has(t.id));
    
    if (tripsToBill.length === 0) {
      alert("Nenhuma viagem selecionada para faturar.");
      return;
    }

    setProcessingClient(clientName);
    try {
      const tripIds = tripsToBill.map(t => t.id);
      
      const date = new Date();
      const firstDay = new Date(date.getFullYear(), date.getMonth(), 1).toISOString();
      const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0, 23, 59, 59).toISOString();

      await createBillingDocument({
        contract_id: tripsToBill[0].contractId || null,
        client_nuit: null,
        client_name: clientName,
        contract_reference: tripsToBill[0].contractReference || null,
        billing_period_start: periodStart ? new Date(periodStart).toISOString() : firstDay,
        billing_period_end: periodEnd ? new Date(periodEnd + "T23:59:59").toISOString() : lastDay,
        currency: "MZN",
        trip_ids: tripIds,
      });

      await loadTrips();
      alert(`Fatura gerada com sucesso para ${clientName} (${tripsToBill.length} Guias)!`);
    } catch (error) {
      alert("Erro ao gerar fatura. Tente novamente.");
    } finally {
      setProcessingClient(null);
    }
  };

  // Agrupar as viagens por client_name
  const groupedTrips = useMemo(() => {
    return trips.reduce((acc, trip) => {
      const key = trip.client || "Cliente Não Definido";
      if (!acc[key]) acc[key] = [];
      acc[key].push(trip);
      return acc;
    }, {} as Record<string, BillingTrip[]>);
  }, [trips]);

  return (
    <div className="space-y-6">
      
      {/* Barra de Filtros */}
      <div className="bg-surface-2 p-4 rounded-lg border border-border flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs font-semibold text-muted mb-1 uppercase tracking-wider">Entregas Desde</label>
          <div className="relative">
            <Calendar className="absolute left-3 top-2.5 text-muted" size={16} />
            <input 
              type="date" 
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="pl-9 pr-4 py-2 bg-surface border border-border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none text-ink w-40"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-semibold text-muted mb-1 uppercase tracking-wider">Entregas Até</label>
          <div className="relative">
            <Calendar className="absolute left-3 top-2.5 text-muted" size={16} />
            <input 
              type="date" 
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="pl-9 pr-4 py-2 bg-surface border border-border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none text-ink w-40"
            />
          </div>
        </div>
        <button 
          onClick={loadTrips}
          className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded-lg text-sm font-semibold transition-colors"
        >
          <Filter size={16} /> Aplicar Filtros
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center items-center py-12">
          <Loader2 className="animate-spin text-blue-500" size={32} />
        </div>
      ) : trips.length === 0 ? (
        <div className="text-center py-12 text-muted bg-surface-2 rounded-lg border border-border border-dashed">
          <Truck size={48} className="mx-auto mb-4 opacity-30" />
          <h3 className="text-lg font-semibold text-ink">Nenhuma Viagem Encontrada</h3>
          <p>Não há entregas faturáveis no período selecionado.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedTrips).map(([clientName, clientTrips]) => {
            
            const selectedTrips = clientTrips.filter(t => selectedIds.has(t.id));
            const isAllSelected = selectedTrips.length === clientTrips.length;
            const totalRevenue = selectedTrips.reduce((sum, trip) => sum + Number(trip.amount || 0), 0);
            const isProcessing = processingClient === clientName;

            return (
              <div key={clientName} className="border border-border rounded-lg overflow-hidden bg-surface shadow-sm">
                
                {/* Header do Cliente */}
                <div className="p-4 bg-surface-2 border-b border-border flex justify-between items-center">
                  <div>
                    <h3 className="text-lg font-bold text-ink">{clientName}</h3>
                    <p className="text-sm text-muted">
                      {selectedTrips.length} de {clientTrips.length} Guias selecionadas
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted">Valor Total a Faturar</p>
                    <p className="text-xl font-bold text-emerald-600">
                      {totalRevenue.toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                    </p>
                  </div>
                </div>

                {/* Tabela de Viagens */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-surface text-xs uppercase text-muted border-b border-border">
                      <tr>
                        <th className="px-4 py-3 w-10">
                          <button onClick={() => toggleClientSelection(clientTrips, isAllSelected)} className="text-muted hover:text-blue-500">
                            {isAllSelected ? <CheckSquare size={18} className="text-blue-600"/> : <Square size={18} />}
                          </button>
                        </th>
                        <th className="px-4 py-3 font-semibold">Origem → Destino</th>
                        <th className="px-4 py-3 font-semibold">Referência do Contrato</th>
                        <th className="px-4 py-3 text-right font-semibold">Valor da Viagem</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {clientTrips.map((trip) => {
                        const isSelected = selectedIds.has(trip.id);
                        return (
                          <tr key={trip.id} className={`hover:bg-muted/10 transition-colors ${isSelected ? 'bg-blue-50/30' : ''}`}>
                            <td className="px-4 py-3">
                              <button onClick={() => toggleSelection(trip.id)} className="text-muted hover:text-blue-500">
                                {isSelected ? <CheckSquare size={18} className="text-blue-600"/> : <Square size={18} />}
                              </button>
                            </td>
                            <td className="px-4 py-3 font-medium text-ink">
                              {trip.route}
                            </td>
                            <td className="px-4 py-3 font-mono text-xs text-muted">
                              {trip.contractReference || "-"}
                            </td>
                            <td className="px-4 py-3 text-right font-mono font-medium text-ink">
                              {Number(trip.amount || 0).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Botão de Ação */}
                <div className="p-4 bg-surface border-t border-border">
                  <button
                    onClick={() => handleCreateDocument(clientName, clientTrips)}
                    disabled={isProcessing || selectedTrips.length === 0}
                    className="w-full flex items-center justify-center gap-2 py-3 bg-ink hover:bg-zinc-800 disabled:bg-surface-2 disabled:text-muted disabled:cursor-not-allowed text-white rounded-lg font-semibold transition-colors"
                  >
                    {isProcessing ? (
                      <><Loader2 className="animate-spin" size={18} /> A Gerar Fatura e Emitir...</>
                    ) : (
                      <><Calculator size={18} /> Emitir Fatura Consolidada ({selectedTrips.length} Guias)</>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
