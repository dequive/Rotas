"use client";

import { useEffect, useState } from "react";
import { Loader2, TrendingUp, TrendingDown, DollarSign } from "lucide-react";
import { bffRequest } from "@/app/lib/bff";

export default function TabFinance({ vehicleId }: { vehicleId: string }) {
  const [pl, setPl] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const res = await bffRequest(`/api/v1/accounting/profit-and-loss?vehicle_id=${vehicleId}`);
        if (res.ok) {
          const data = await res.json();
          setPl(data);
        }
      } catch (err) {
        console.error("Failed to load P&L data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [vehicleId]);

  if (loading) {
    return <div className="p-12 flex justify-center"><Loader2 className="animate-spin text-slate-400" size={32} /></div>;
  }

  if (!pl) {
    return <div className="p-12 text-center text-slate-500">Sem dados financeiros para esta viatura.</div>;
  }

  // Helper to format currency
  const formatMoney = (val: number) => {
    return new Intl.NumberFormat("pt-MZ", { style: "currency", currency: "MZN" }).format(val || 0);
  };

  const isProfit = pl.net_income >= 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Receitas */}
        <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp size={20} className="text-emerald-600" />
            <h3 className="text-sm font-bold text-emerald-900 uppercase tracking-wide">Faturação Gerada</h3>
          </div>
          <p className="text-3xl font-black text-emerald-700">{formatMoney(pl.total_revenue)}</p>
          <p className="text-xs text-emerald-600/80 mt-1">Fretes e serviços faturados</p>
        </div>

        {/* Despesas */}
        <div className="bg-rose-50 border border-rose-100 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown size={20} className="text-rose-600" />
            <h3 className="text-sm font-bold text-rose-900 uppercase tracking-wide">Custos Operacionais</h3>
          </div>
          <p className="text-3xl font-black text-rose-700">{formatMoney(pl.total_expenses)}</p>
          <p className="text-xs text-rose-600/80 mt-1">Combustível, manutenção e impostos</p>
        </div>

        {/* EBITDA / Net Income */}
        <div className={`${isProfit ? "bg-indigo-900 border-indigo-800" : "bg-slate-900 border-slate-800"} rounded-2xl p-6 shadow-sm text-white`}>
          <div className="flex items-center gap-2 mb-2">
            <DollarSign size={20} className={isProfit ? "text-indigo-300" : "text-slate-400"} />
            <h3 className={`text-sm font-bold uppercase tracking-wide ${isProfit ? "text-indigo-200" : "text-slate-300"}`}>
              Lucro / Prejuízo (EBITDA)
            </h3>
          </div>
          <p className="text-3xl font-black">{formatMoney(pl.net_income)}</p>
          <p className={`text-xs mt-1 ${isProfit ? "text-indigo-300" : "text-slate-400"}`}>Resultado líquido alocado</p>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
         <h3 className="text-lg font-bold text-slate-900 mb-4">Estrutura de Custos (PGC-NIRF)</h3>
         {pl.expenses_breakdown && Object.keys(pl.expenses_breakdown).length > 0 ? (
           <div className="space-y-3">
             {Object.entries(pl.expenses_breakdown).map(([account, amount]: any) => (
               <div key={account} className="flex justify-between items-center py-2 border-b border-slate-100 last:border-0">
                 <span className="text-sm font-medium text-slate-700">{account}</span>
                 <span className="text-sm font-bold text-rose-600">{formatMoney(amount)}</span>
               </div>
             ))}
           </div>
         ) : (
           <p className="text-sm text-slate-500">Nenhum custo registado na contabilidade.</p>
         )}
      </div>
    </div>
  );
}
