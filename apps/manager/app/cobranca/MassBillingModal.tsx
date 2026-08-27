"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { ReceiptText, Loader2, Filter, CalendarDays, Calculator } from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import { BillingTrip } from "@/app/lib/billing-api";
import { bffRequest } from "@/app/lib/bff";

export function MassBillingModal({ trips }: { trips: BillingTrip[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters state
  const [selectedClient, setSelectedClient] = useState<string>("");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  // Only consider billable trips
  const billableTrips = useMemo(() => trips.filter(t => t.status === "billable"), [trips]);

  // Unique clients
  const uniqueClients = useMemo(() => {
    const clients = new Set(billableTrips.map(t => t.client ?? "Cliente Desconhecido"));
    return Array.from(clients).sort();
  }, [billableTrips]);

  // Derived filtered trips based on form state
  const filteredTrips = useMemo(() => {
    return billableTrips.filter(t => {
      const clientName = t.client ?? "Cliente Desconhecido";
      if (selectedClient && clientName !== selectedClient) return false;
      if (startDate && t.deliveredAt < startDate) return false;
      if (endDate && t.deliveredAt > endDate) return false;
      return true;
    });
  }, [billableTrips, selectedClient, startDate, endDate]);

  const totalAmount = useMemo(() => {
    return filteredTrips.reduce((acc, trip) => acc + (trip.amount ?? 0), 0);
  }, [filteredTrips]);

  const formatMoney = (val: number) => {
    return new Intl.NumberFormat("pt-MZ", { style: "currency", currency: "MZN" }).format(val);
  };

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (filteredTrips.length === 0) return;
    
    setLoading(true);
    setError(null);

    // Group trips by client (in case they didn't filter by a specific client)
    const tripsByClient = filteredTrips.reduce((acc, trip) => {
      const client = trip.client ?? "Cliente Desconhecido";
      if (!acc[client]) acc[client] = [];
      acc[client].push(trip);
      return acc;
    }, {} as Record<string, BillingTrip[]>);

    try {
      const headers = {
        "Content-Type": "application/json"
      };

      for (const [clientName, clientTrips] of Object.entries(tripsByClient)) {
        // If they filtered by dates, use those, else use defaults
        const sDate = startDate ? new Date(startDate).toISOString() : new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
        const eDate = endDate ? new Date(endDate).toISOString() : new Date().toISOString();

        const payload = {
          client_name: clientName,
          billing_period_start: sDate,
          billing_period_end: eDate,
          currency: "MZN",
          trip_ids: clientTrips.map(t => t.id),
          client_nuit: "000000000" // Bypass draft NUIT validation
        };

        const res = await bffRequest("/api/v1/billing/documents", {
          method: "POST",
          headers,
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          throw new Error(`Erro ao gerar fatura para ${clientName}`);
        }
      }

      setOpen(false);
      router.refresh();
      
      // Reset form
      setSelectedClient("");
      setStartDate("");
      setEndDate("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (billableTrips.length === 0) {
    return (
      <button
        disabled
        className="inline-flex items-center gap-1.5 h-9 px-4 text-[13px] font-semibold bg-indigo-600/50 text-white border-0 rounded-md cursor-not-allowed"
      >
        <ReceiptText size={15} />
        Faturação em Lote
      </button>
    );
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          className="inline-flex items-center gap-1.5 h-9 px-4 text-[13px] font-semibold bg-indigo-600 hover:bg-indigo-700 text-white border-0 rounded-md shadow-sm transition-colors"
        >
          <ReceiptText size={15} />
          Faturação em Lote
        </button>
      </Dialog.Trigger>
      
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 transition-opacity" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg bg-white rounded-3xl p-6 shadow-2xl z-50">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center">
              <ReceiptText size={20} />
            </div>
            <div>
              <Dialog.Title className="text-xl font-black text-slate-900">
                Assistente de Faturação
              </Dialog.Title>
              <Dialog.Description className="text-sm font-medium text-slate-500">
                Agrupe múltiplas viagens numa única fatura inteligente.
              </Dialog.Description>
            </div>
          </div>

          <form onSubmit={handleGenerate} className="space-y-5">
            {error && (
              <div className="bg-rose-50 border border-rose-200 text-rose-700 px-3 py-2 rounded-lg text-sm font-bold">
                {error}
              </div>
            )}

            <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 space-y-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1">
                  <Filter size={14} /> Cliente Alvo (Opcional)
                </label>
                <select 
                  value={selectedClient}
                  onChange={(e) => setSelectedClient(e.target.value)}
                  className="h-11 w-full bg-white border border-slate-200 rounded-xl px-3 text-sm font-bold text-slate-900 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 transition-shadow"
                >
                  <option value="">Faturar todos os clientes disponíveis</option>
                  {uniqueClients.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1">
                    <CalendarDays size={14} /> Descargas de:
                  </label>
                  <input 
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="h-11 w-full bg-white border border-slate-200 rounded-xl px-3 text-sm font-bold text-slate-900 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 transition-shadow"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1">
                    <CalendarDays size={14} /> Descargas até:
                  </label>
                  <input 
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="h-11 w-full bg-white border border-slate-200 rounded-xl px-3 text-sm font-bold text-slate-900 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 transition-shadow"
                  />
                </div>
              </div>
            </div>

            {/* Sumário em Tempo Real */}
            <div className={`p-4 rounded-2xl flex items-center justify-between border ${filteredTrips.length > 0 ? "bg-emerald-50 border-emerald-200" : "bg-slate-100 border-slate-200"}`}>
               <div className="flex items-center gap-3">
                 <div className={`w-10 h-10 rounded-full flex items-center justify-center ${filteredTrips.length > 0 ? "bg-emerald-200 text-emerald-700" : "bg-slate-200 text-slate-400"}`}>
                   <Calculator size={20} />
                 </div>
                 <div>
                   <p className={`text-sm font-bold ${filteredTrips.length > 0 ? "text-emerald-900" : "text-slate-500"}`}>
                     {filteredTrips.length} Viagens Encontradas
                   </p>
                   <p className={`text-xs ${filteredTrips.length > 0 ? "text-emerald-700" : "text-slate-400"}`}>
                     Prontas para compilar
                   </p>
                 </div>
               </div>
               <div className="text-right">
                 <p className={`text-lg font-black ${filteredTrips.length > 0 ? "text-emerald-700" : "text-slate-400"}`}>
                   {formatMoney(totalAmount)}
                 </p>
                 <p className={`text-xs ${filteredTrips.length > 0 ? "text-emerald-600/70" : "text-slate-400"}`}>
                   Valor Bruto
                 </p>
               </div>
            </div>

            <div className="pt-2 flex gap-3">
              <Dialog.Close asChild>
                <button type="button" className="flex-1 h-12 rounded-xl font-bold border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors">Cancelar</button>
              </Dialog.Close>
              <button 
                type="submit" 
                disabled={loading || filteredTrips.length === 0} 
                className={`flex-1 h-12 rounded-xl font-bold text-white shadow-lg transition-colors flex items-center justify-center gap-2 ${filteredTrips.length > 0 ? "bg-indigo-600 hover:bg-indigo-700 shadow-indigo-600/20" : "bg-slate-400 cursor-not-allowed shadow-none"}`}
              >
                {loading && <Loader2 className="animate-spin" size={20} />}
                {loading ? "A Processar..." : "Agrupar Faturas"}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
