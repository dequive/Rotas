"use client";

import { useState } from "react";
import { X, CheckCircle, UserPlus, FileText, BadgePercent } from "lucide-react";
import { createEmployee } from "../../lib/hr-api";

export function NewEmployeeModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [employeeNumber, setEmployeeNumber] = useState("");
  
  const [role, setRole] = useState("");
  const [department, setDepartment] = useState("");
  const [professionalCategory, setProfessionalCategory] = useState("");
  
  const [baseSalary, setBaseSalary] = useState("");
  const [irpsTax, setIrpsTax] = useState("0");
  
  const [nuit, setNuit] = useState("");
  const [inssNumber, setInssNumber] = useState("");
  
  const [hireDate, setHireDate] = useState(new Date().toISOString().slice(0, 10));

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await createEmployee({
        first_name: firstName,
        last_name: lastName,
        employee_number: employeeNumber || null,
        role,
        department,
        professional_category: professionalCategory || null,
        base_salary: Number(baseSalary),
        irps_tax_percentage: Number(irpsTax),
        nif_nuit: nuit || null,
        inss_beneficiary_number: inssNumber || null,
        hire_date: new Date(hireDate).toISOString().slice(0, 10),
      });
      onSuccess();
    } catch (err) {
      alert("Erro ao criar colaborador. Verifique os dados.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-surface rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden border border-border my-8">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-surface-2 sticky top-0 z-10">
          <h3 className="font-semibold text-lg flex items-center gap-2">
            <UserPlus className="text-blue-600" /> Ficha de Colaborador Completa
          </h3>
          <button onClick={onClose} className="text-muted hover:text-ink"><X size={20} /></button>
        </div>

        <form onSubmit={handleSave} className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          
          {/* IDENTIFICAÇÃO */}
          <div>
            <h4 className="text-sm font-bold text-ink mb-3 flex items-center gap-2"><UserPlus size={16}/> Dados Pessoais</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="md:col-span-1">
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Nº Empregado</label>
                <input
                  type="text"
                  placeholder="Ex: 01"
                  value={employeeNumber}
                  onChange={e => setEmployeeNumber(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div className="md:col-span-1">
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Nome Próprio</label>
                <input
                  type="text"
                  required
                  value={firstName}
                  onChange={e => setFirstName(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div className="md:col-span-1">
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Apelido</label>
                <input
                  type="text"
                  required
                  value={lastName}
                  onChange={e => setLastName(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
          </div>

          <hr className="border-border" />

          {/* VÍNCULO */}
          <div>
            <h4 className="text-sm font-bold text-ink mb-3 flex items-center gap-2"><FileText size={16}/> Vínculo à Empresa</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Departamento</label>
                <select 
                  required
                  value={department}
                  onChange={e => setDepartment(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">Selecione...</option>
                  <option value="Operações (Motoristas)">Operações (Motoristas)</option>
                  <option value="Oficina e Manutenção">Oficina e Manutenção</option>
                  <option value="Administração e Finanças">Administração e Finanças</option>
                  <option value="Recursos Humanos">Recursos Humanos</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Cargo (Função)</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Motorista de Pesados"
                  value={role}
                  onChange={e => setRole(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Categoria Profissional</label>
                <input
                  type="text"
                  placeholder="Ex: Administrador"
                  value={professionalCategory}
                  onChange={e => setProfessionalCategory(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
          </div>

          <hr className="border-border" />

          {/* REMUNERAÇÃO E FISCALIDADE */}
          <div>
            <h4 className="text-sm font-bold text-ink mb-3 flex items-center gap-2"><BadgePercent size={16}/> Remuneração e Fiscalidade</h4>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div className="md:col-span-2">
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Salário Base Mensal (MZN)</label>
                <input
                  type="number"
                  required
                  min="0"
                  step="0.01"
                  value={baseSalary}
                  onChange={e => setBaseSalary(e.target.value)}
                  className="w-full border border-blue-300 bg-blue-50/30 rounded-lg px-3 py-2 text-lg font-bold text-ink"
                />
              </div>
              <div className="md:col-span-1">
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Taxa IRPS (%)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={irpsTax}
                  onChange={e => setIrpsTax(e.target.value)}
                  className="w-full border border-red-200 bg-red-50/30 rounded-lg px-3 py-2 text-lg font-bold text-red-600"
                />
              </div>
              <div className="md:col-span-1">
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Data Admissão</label>
                <input
                  type="date"
                  required
                  value={hireDate}
                  onChange={e => setHireDate(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm h-11"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
               <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Nº Contribuinte (NUIT)</label>
                <input
                  type="text"
                  value={nuit}
                  onChange={e => setNuit(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Nº Beneficiário (INSS)</label>
                <input
                  type="text"
                  value={inssNumber}
                  onChange={e => setInssNumber(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm font-mono"
                />
              </div>
            </div>
          </div>

          <div className="pt-4 flex justify-end gap-2 sticky bottom-0 bg-surface">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium border border-border rounded-lg hover:bg-muted"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
            >
              {loading ? "A guardar..." : <><CheckCircle size={16} /> Salvar Ficha de Funcionário</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
