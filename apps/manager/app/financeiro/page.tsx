"use client";

import { useState, useEffect, useCallback } from "react";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { TrendingUp, TrendingDown, DollarSign, Calendar, Landmark } from "lucide-react";
import { bffRequest } from "@/app/lib/bff";

// Helper function to format MZN
function fmtMZN(value: number) {
  return new Intl.NumberFormat("pt-MZ", {
    style: "currency",
    currency: "MZN",
    minimumFractionDigits: 2,
  }).format(value);
}

interface DreLine {
  account_id: string;
  code: string;
  name: string;
  balance: number;
}

interface DreResponse {
  total_revenue: number;
  total_expense: number;
  ebitda: number;
  lines: DreLine[];
}

export default function FinanceiroDashboard() {
  const [data, setData] = useState<DreResponse | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Filtros
  const [month, setMonth] = useState<string>(new Date().getMonth() + 1 + "");
  const [year, setYear] = useState<string>(new Date().getFullYear() + "");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (month && month !== "all") params.append("month", month);
      if (year) params.append("year", year);
      const query = params.size ? `?${params}` : "";
      const res = await bffRequest(`/api/v1/accounting/profit-and-loss${query}`);
      if (res.ok) {
        setData(await res.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [month, year]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <SidebarLayout active="financeiro">
      <div className="p-6 max-w-7xl mx-auto flex flex-col gap-8 h-full">
        {/* Header & Filters */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <Landmark className="text-green-600" /> Visão Financeira (DRE)
            </h1>
            <p className="text-slate-500 mt-1">
              Demonstração de Resultados (Profit & Loss) da sua empresa em tempo real.
            </p>
          </div>
          
          <div className="flex items-center gap-3 bg-white p-2 rounded-xl shadow-sm border border-slate-200">
            <div className="flex items-center gap-2 px-2 text-slate-500">
              <Calendar size={18} />
            </div>
            <select 
              value={month} 
              onChange={e => setMonth(e.target.value)}
              className="bg-slate-50 border-none text-sm font-semibold text-slate-700 py-1.5 px-3 rounded cursor-pointer outline-none focus:ring-2 focus:ring-green-500"
            >
              <option value="all">Ano Inteiro (YTD)</option>
              <option value="1">Janeiro</option>
              <option value="2">Fevereiro</option>
              <option value="3">Março</option>
              <option value="4">Abril</option>
              <option value="5">Maio</option>
              <option value="6">Junho</option>
              <option value="7">Julho</option>
              <option value="8">Agosto</option>
              <option value="9">Setembro</option>
              <option value="10">Outubro</option>
              <option value="11">Novembro</option>
              <option value="12">Dezembro</option>
            </select>
            <select 
              value={year} 
              onChange={e => setYear(e.target.value)}
              className="bg-slate-50 border-none text-sm font-semibold text-slate-700 py-1.5 px-3 rounded cursor-pointer outline-none focus:ring-2 focus:ring-green-500"
            >
              <option value="2026">2026</option>
              <option value="2027">2027</option>
            </select>
          </div>
        </div>

        {/* KPI Cards */}
        {loading ? (
          <div className="animate-pulse flex gap-4">
            <div className="h-32 bg-slate-200 rounded-2xl flex-1"></div>
            <div className="h-32 bg-slate-200 rounded-2xl flex-1"></div>
            <div className="h-32 bg-slate-200 rounded-2xl flex-1"></div>
          </div>
        ) : data ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-6 opacity-10 group-hover:opacity-20 transition-opacity">
                <TrendingUp size={64} className="text-emerald-500" />
              </div>
              <p className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-2">Total Rendimentos</p>
              <h2 className="text-3xl font-black text-slate-800">{fmtMZN(data.total_revenue)}</h2>
              <p className="text-xs text-slate-400 mt-2 font-medium">Faturação e proveitos operacionais.</p>
            </div>

            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-6 opacity-10 group-hover:opacity-20 transition-opacity">
                <TrendingDown size={64} className="text-rose-500" />
              </div>
              <p className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-2">Total Gastos</p>
              <h2 className="text-3xl font-black text-slate-800">{fmtMZN(data.total_expense)}</h2>
              <p className="text-xs text-slate-400 mt-2 font-medium">Custos de frota, manutenção e estrutura.</p>
            </div>

            <div className={`rounded-2xl p-6 shadow-sm border relative overflow-hidden group ${data.ebitda >= 0 ? 'bg-slate-900 border-slate-800' : 'bg-rose-600 border-rose-700'}`}>
              <div className="absolute top-0 right-0 p-6 opacity-20 group-hover:opacity-30 transition-opacity">
                <DollarSign size={64} className="text-white" />
              </div>
              <p className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2 text-white/70">EBITDA (Margem Bruta)</p>
              <h2 className="text-3xl font-black text-white">{fmtMZN(data.ebitda)}</h2>
              <p className="text-xs text-slate-400 mt-2 font-medium text-white/50">O lucro gerado pela operação.</p>
            </div>
            
          </div>
        ) : null}

        {/* Detailed Accounts Table */}
        {!loading && data && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-5 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
              <h3 className="font-bold text-slate-800">Desagregação Analítica (PGC-NIRF)</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-white border-b border-slate-200">
                    <th className="py-3 px-5 text-xs font-bold text-slate-500 uppercase tracking-wider">Conta</th>
                    <th className="py-3 px-5 text-xs font-bold text-slate-500 uppercase tracking-wider">Descrição</th>
                    <th className="py-3 px-5 text-xs font-bold text-slate-500 uppercase tracking-wider text-right">Saldo Período</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.lines.map((line) => (
                    <tr key={line.account_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-5">
                        <span className="font-mono text-sm font-bold text-indigo-600 bg-indigo-50 px-2 py-1 rounded">
                          {line.code}
                        </span>
                      </td>
                      <td className="py-3 px-5 font-medium text-slate-700">
                        {line.name}
                      </td>
                      <td className={`py-3 px-5 text-right font-mono font-bold ${line.code.startsWith("7") ? "text-emerald-600" : "text-rose-600"}`}>
                        {fmtMZN(line.balance)}
                      </td>
                    </tr>
                  ))}
                  {data.lines.length === 0 && (
                    <tr>
                      <td colSpan={3} className="py-12 text-center text-slate-500 font-medium">
                        Nenhum movimento contabilístico registado neste período.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </SidebarLayout>
  );
}
