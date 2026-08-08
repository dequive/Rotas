"use client";

import { useState, useEffect, useCallback } from "react";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { BookOpen, Search } from "lucide-react";
import { bffRequest } from "@/app/lib/bff";

function fmtMZN(value: number) {
  return new Intl.NumberFormat("pt-MZ", {
    style: "currency",
    currency: "MZN",
    minimumFractionDigits: 2,
  }).format(value);
}

interface TrialBalanceLine {
  account_id: string;
  code: string;
  name: string;
  debit_total: number;
  credit_total: number;
  balance: number;
}

export default function BalanceteERazao() {
  const [data, setData] = useState<TrialBalanceLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await bffRequest("/api/v1/accounting/trial-balance");
      if (res.ok) {
        setData(await res.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filteredData = data.filter(line => 
    line.code.includes(searchTerm) || 
    line.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <SidebarLayout active="contabilidade">
      <div className="p-6 max-w-7xl mx-auto flex flex-col gap-6 h-full">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <BookOpen className="text-indigo-600" /> Balancete e Razão Geral
            </h1>
            <p className="text-slate-500 mt-1">
              Verificação dos saldos das contas PGC-NIRF do seu Plano de Contas.
            </p>
          </div>
          
          <div className="relative w-full md:w-64">
            <Search className="absolute left-3 top-2.5 text-slate-400" size={18} />
            <input 
              type="text" 
              placeholder="Pesquisar conta..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full h-10 pl-10 pr-3 bg-white border border-slate-200 rounded-lg text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
            />
          </div>
        </div>

        {loading ? (
          <div className="animate-pulse bg-white rounded-2xl h-96 border border-slate-200"></div>
        ) : (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200">
                    <th className="py-3 px-5 text-xs font-bold text-slate-500 uppercase tracking-wider">Conta</th>
                    <th className="py-3 px-5 text-xs font-bold text-slate-500 uppercase tracking-wider">Descrição</th>
                    <th className="py-3 px-5 text-xs font-bold text-slate-500 uppercase tracking-wider text-right">Total Débito</th>
                    <th className="py-3 px-5 text-xs font-bold text-slate-500 uppercase tracking-wider text-right">Total Crédito</th>
                    <th className="py-3 px-5 text-xs font-bold text-slate-500 uppercase tracking-wider text-right">Saldo Final</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredData.map((line) => (
                    <tr key={line.account_id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-3 px-5">
                        <span className="font-mono text-sm font-bold text-slate-600 bg-slate-100 px-2 py-1 rounded">
                          {line.code}
                        </span>
                      </td>
                      <td className="py-3 px-5 font-medium text-slate-700">
                        {line.name}
                      </td>
                      <td className="py-3 px-5 text-right font-mono text-slate-600 text-sm">
                        {fmtMZN(line.debit_total)}
                      </td>
                      <td className="py-3 px-5 text-right font-mono text-slate-600 text-sm">
                        {fmtMZN(line.credit_total)}
                      </td>
                      <td className={`py-3 px-5 text-right font-mono font-bold text-sm ${line.balance >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {fmtMZN(line.balance)}
                      </td>
                    </tr>
                  ))}
                  {filteredData.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-12 text-center text-slate-500 font-medium">
                        Nenhuma conta encontrada.
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
