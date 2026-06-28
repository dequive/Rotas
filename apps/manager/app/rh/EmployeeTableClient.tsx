"use client";

import { useState } from "react";
import { UserPlus, Search, Briefcase } from "lucide-react";
import { Employee } from "../../lib/hr-api";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { NewEmployeeModal } from "./NewEmployeeModal";

export function EmployeeTableClient({ initialEmployees }: { initialEmployees: Employee[] }) {
  const [search, setSearch] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);

  const filtered = initialEmployees.filter(emp => 
    emp.first_name.toLowerCase().includes(search.toLowerCase()) || 
    emp.last_name.toLowerCase().includes(search.toLowerCase()) ||
    emp.role.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center bg-surface border border-border p-4 rounded-lg">
        <div className="relative w-full sm:max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={18} />
          <input
            type="text"
            placeholder="Pesquisar por nome ou cargo..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-border rounded-lg text-sm bg-surface-2 focus:bg-surface focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
          />
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors whitespace-nowrap"
        >
          <UserPlus size={18} /> Adicionar Colaborador
        </button>
      </div>

      <div className="bg-surface border border-border rounded-lg overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-xs uppercase text-muted border-b border-border">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Nome</th>
                <th className="px-4 py-3 text-left font-semibold">Departamento</th>
                <th className="px-4 py-3 text-left font-semibold">Cargo</th>
                <th className="px-4 py-3 text-right font-semibold">Salário Base Mensal</th>
                <th className="px-4 py-3 text-center font-semibold">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-muted">
                    Nenhum colaborador encontrado.
                  </td>
                </tr>
              ) : (
                filtered.map(emp => (
                  <tr key={emp.id} className="hover:bg-muted/30 transition-colors cursor-pointer">
                    <td className="px-4 py-3 font-semibold text-ink flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs">
                        {emp.first_name[0]}{emp.last_name[0]}
                      </div>
                      {emp.first_name} {emp.last_name}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      <span className="flex items-center gap-1.5"><Briefcase size={14}/> {emp.department}</span>
                    </td>
                    <td className="px-4 py-3 text-muted">{emp.role}</td>
                    <td className="px-4 py-3 text-right font-mono font-medium text-ink">
                      {Number(emp.base_salary).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <StatusBadge 
                        status={emp.status === "active" ? "concluida" : "erro"} 
                        label={emp.status === "active" ? "Ativo" : "Desligado"} 
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {isModalOpen && (
        <NewEmployeeModal
          onClose={() => setIsModalOpen(false)}
          onSuccess={() => window.location.reload()}
        />
      )}
    </div>
  );
}
