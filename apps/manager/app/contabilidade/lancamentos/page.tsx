"use client";

import { useState, useEffect, useCallback } from "react";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { Save, Plus, Trash2, CheckCircle2 } from "lucide-react";

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("rotas_access_token");
  const tenantId = localStorage.getItem("rotas_tenant_id");
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(tenantId ? { "X-Tenant-Id": tenantId } : {}),
  };
}

function getApiBase(): string {
  if (typeof window === "undefined") return "";
  return (
    localStorage.getItem("rotas_api_base_url") ??
    (process.env.NEXT_PUBLIC_ROTAS_API_BASE_URL ?? "")
  );
}

interface Account {
  id: string;
  code: string;
  name: string;
}

export default function LançamentosManuais() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  
  const [date, setDate] = useState("");
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");
  const [journalType, setJournalType] = useState("OD");
  
  const [lines, setLines] = useState([
    { id: "1", account_id: "", debit: "", credit: "" },
    { id: "2", account_id: "", debit: "", credit: "" }
  ]);

  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    async function fetchAccounts() {
      try {
        const res = await fetch(`${getApiBase()}/api/v1/accounting/accounts`, {
          headers: getAuthHeaders()
        });
        if (res.ok) {
          setAccounts(await res.json());
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoadingAccounts(false);
      }
    }
    fetchAccounts();
    setDate(new Date().toISOString().split('T')[0]);
  }, []);

  const totalDebit = lines.reduce((acc, l) => acc + (parseFloat(l.debit) || 0), 0);
  const totalCredit = lines.reduce((acc, l) => acc + (parseFloat(l.credit) || 0), 0);
  const isBalanced = totalDebit > 0 && totalDebit === totalCredit;

  const handleAddLine = () => {
    setLines([...lines, { id: Math.random().toString(), account_id: "", debit: "", credit: "" }]);
  };

  const handleRemoveLine = (id: string) => {
    if (lines.length > 2) {
      setLines(lines.filter(l => l.id !== id));
    }
  };

  const updateLine = (id: string, field: string, value: string) => {
    setLines(lines.map(l => l.id === id ? { ...l, [field]: value } : l));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isBalanced) {
      alert("O lançamento não bate certo. Débitos devem igualar Créditos.");
      return;
    }
    
    // Filter out empty lines
    const validLines = lines.filter(l => l.account_id && (parseFloat(l.debit) > 0 || parseFloat(l.credit) > 0));

    setSaving(true);
    try {
      const res = await fetch(`${getApiBase()}/api/v1/accounting/manual-entry`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders()
        },
        body: JSON.stringify({
          journal_type: journalType,
          date: new Date(date).toISOString(),
          reference,
          description,
          items: validLines.map(l => ({
            account_id: l.account_id,
            debit: parseFloat(l.debit) || 0,
            credit: parseFloat(l.credit) || 0
          }))
        })
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Erro ao gravar lançamento.");
      }

      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        setReference("");
        setDescription("");
        setLines([
          { id: Math.random().toString(), account_id: "", debit: "", credit: "" },
          { id: Math.random().toString(), account_id: "", debit: "", credit: "" }
        ]);
      }, 3000);

    } catch (e: any) {
      console.error(e);
      alert(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <SidebarLayout active="contabilidade">
      <div className="p-6 max-w-5xl mx-auto flex flex-col gap-6 h-full">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Lançamentos Manuais</h1>
            <p className="text-slate-500 mt-1">
              Ferramenta avançada para contabilistas (Partidas Dobradas PGC-NIRF).
            </p>
          </div>
        </div>

        {success ? (
          <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-12 flex flex-col items-center justify-center text-center shadow-sm">
            <CheckCircle2 size={48} className="text-emerald-500 mb-4" />
            <h3 className="text-xl font-bold text-emerald-900">Lançamento Gravado no Livro Razão!</h3>
            <p className="text-emerald-700 mt-2">
              As contas foram atualizadas com sucesso e já refletem no Balancete.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6 flex flex-col gap-6">
            
            {/* Header Form */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Data do Registo *</label>
                <input 
                  type="date" required value={date} onChange={e => setDate(e.target.value)}
                  className="h-10 px-3 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none w-full text-sm font-medium"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Diário *</label>
                <select 
                  value={journalType} onChange={e => setJournalType(e.target.value)}
                  className="h-10 px-3 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none w-full text-sm font-medium bg-white"
                >
                  <option value="OD">Operações Diversas (OD)</option>
                  <option value="TES">Tesouraria (TES)</option>
                  <option value="COM">Compras (COM)</option>
                  <option value="VEN">Vendas (VEN)</option>
                </select>
              </div>
              <div className="flex flex-col gap-1.5 md:col-span-2">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Documento / Referência</label>
                <input 
                  type="text" placeholder="Ex: Fatura Eletricidade #9822" value={reference} onChange={e => setReference(e.target.value)}
                  className="h-10 px-3 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none w-full text-sm font-medium"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Descrição Histórica *</label>
              <input 
                type="text" required placeholder="Anotação que aparecerá no Livro Razão" value={description} onChange={e => setDescription(e.target.value)}
                className="h-10 px-3 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none w-full text-sm font-medium"
              />
            </div>

            {/* Lines */}
            <div className="border border-slate-200 rounded-xl overflow-hidden mt-4">
              <div className="bg-slate-50 border-b border-slate-200 px-4 py-3 grid grid-cols-12 gap-4 text-xs font-bold text-slate-500 uppercase tracking-wider">
                <div className="col-span-6">Conta PGC-NIRF</div>
                <div className="col-span-2 text-right">Débito (MZN)</div>
                <div className="col-span-2 text-right">Crédito (MZN)</div>
                <div className="col-span-2 text-center">Ações</div>
              </div>
              <div className="flex flex-col divide-y divide-slate-100">
                {lines.map((line, index) => (
                  <div key={line.id} className="p-3 grid grid-cols-12 gap-4 items-center hover:bg-slate-50/50">
                    <div className="col-span-6">
                      <select 
                        required
                        value={line.account_id}
                        onChange={e => updateLine(line.id, "account_id", e.target.value)}
                        className="h-10 px-3 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none w-full text-sm font-medium bg-white"
                      >
                        <option value="">-- Selecione uma conta --</option>
                        {accounts.map(acc => (
                          <option key={acc.id} value={acc.id}>{acc.code} - {acc.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="col-span-2">
                      <input 
                        type="number" step="0.01" min="0" placeholder="0.00"
                        value={line.debit} onChange={e => { updateLine(line.id, "debit", e.target.value); updateLine(line.id, "credit", "0"); }}
                        className="h-10 px-3 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none w-full text-sm font-mono text-right"
                      />
                    </div>
                    <div className="col-span-2">
                      <input 
                        type="number" step="0.01" min="0" placeholder="0.00"
                        value={line.credit} onChange={e => { updateLine(line.id, "credit", e.target.value); updateLine(line.id, "debit", "0"); }}
                        className="h-10 px-3 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none w-full text-sm font-mono text-right"
                      />
                    </div>
                    <div className="col-span-2 flex justify-center">
                      <button 
                        type="button" 
                        onClick={() => handleRemoveLine(line.id)}
                        disabled={lines.length <= 2}
                        className="p-2 text-rose-400 hover:bg-rose-50 hover:text-rose-600 rounded-lg transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="bg-slate-50 border-t border-slate-200 px-4 py-3 flex items-center justify-between">
                <button 
                  type="button" 
                  onClick={handleAddLine}
                  className="text-sm font-bold text-indigo-600 hover:text-indigo-700 flex items-center gap-1.5"
                >
                  <Plus size={16} /> Adicionar Partida
                </button>
                <div className="flex gap-4 items-center">
                  <div className="text-xs font-bold text-slate-500 uppercase">Totais:</div>
                  <div className={`font-mono font-bold ${totalDebit === totalCredit ? 'text-emerald-600' : 'text-rose-600'}`}>
                    D: {totalDebit.toFixed(2)}
                  </div>
                  <div className={`font-mono font-bold ${totalDebit === totalCredit ? 'text-emerald-600' : 'text-rose-600'}`}>
                    C: {totalCredit.toFixed(2)}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end mt-2 pt-4 border-t border-slate-100">
              <button 
                type="submit"
                disabled={saving || !isBalanced}
                className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              >
                {saving ? "A Registar..." : <><Save size={18} /> Lançar na Contabilidade</>}
              </button>
            </div>
          </form>
        )}
      </div>
    </SidebarLayout>
  );
}
