"use client";

import { SidebarLayout } from "@/app/components/SidebarLayout";
import { ArrowLeft, Save, Building, Truck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { bffRequest } from "@/app/lib/bff";

export default function NovaTarefaPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [domain, setDomain] = useState<"fleet" | "internal">("fleet");
  
  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [vehicleId, setVehicleId] = useState(""); // Only for fleet
  
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);

    try {
      if (domain === "fleet") {
        // Send to Workshop API via server action or fetch
        // For the sake of this implementation, we simulate the POST to ROTAS_API_BASE_URL
        await bffRequest("/api/v1/workshop/maintenance-requests", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            vehicle_id: vehicleId,
            description: `${title} - ${description}`,
            priority: "medium",
            reported_by_id: "00000000-0000-0000-0000-000000000000", // Will be replaced by session user id in actual backend
          })
        });
      } else {
        // Send to Governance API via server action or fetch
        await bffRequest("/api/v1/governance/cases", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title,
            description,
            case_type_id: "00000000-0000-0000-0000-000000000000", // Default case type
            status: "pending",
          })
        });
      }

      router.push("/tarefas");
      router.refresh();
    } catch (error) {
      console.error("Failed to create task", error);
      alert("Ocorreu um erro ao criar a tarefa. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <SidebarLayout active="tarefas">
      <div className="p-6 max-w-3xl mx-auto flex flex-col gap-6 h-full">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Link href="/tarefas" className="p-2 hover:bg-slate-100 rounded-full transition-colors">
            <ArrowLeft size={20} className="text-slate-600" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Nova Tarefa</h1>
            <p className="text-slate-500 mt-1">
              Descreva o problema ou pedido. A tarefa será encaminhada para a equipa responsável.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col gap-6">
          
          {/* Domain Selection */}
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => setDomain("fleet")}
              className={`flex-1 p-4 rounded-xl border-2 flex flex-col items-center justify-center gap-3 transition-colors ${
                domain === "fleet" ? "border-indigo-600 bg-indigo-50 text-indigo-700" : "border-slate-200 hover:border-slate-300 text-slate-600"
              }`}
            >
              <Truck size={32} className={domain === "fleet" ? "text-indigo-600" : "text-slate-400"} />
              <div className="text-center">
                <p className="font-semibold">Viatura / Oficina</p>
                <p className="text-xs opacity-80 mt-1">Avarias, reparações ou manutenções de frota</p>
              </div>
            </button>

            <button
              type="button"
              onClick={() => setDomain("internal")}
              className={`flex-1 p-4 rounded-xl border-2 flex flex-col items-center justify-center gap-3 transition-colors ${
                domain === "internal" ? "border-indigo-600 bg-indigo-50 text-indigo-700" : "border-slate-200 hover:border-slate-300 text-slate-600"
              }`}
            >
              <Building size={32} className={domain === "internal" ? "text-indigo-600" : "text-slate-400"} />
              <div className="text-center">
                <p className="font-semibold">Back-office / Instalações</p>
                <p className="text-xs opacity-80 mt-1">Limpezas, pedidos de TI, incidentes de RH</p>
              </div>
            </button>
          </div>

          <hr className="border-slate-100" />

          {/* Dynamic Form Fields */}
          <div className="flex flex-col gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Título Resumido</label>
              <input
                required
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder={domain === "fleet" ? "Ex: Pneu furado na roda traseira direita" : "Ex: Ar condicionado da sala de reuniões avariado"}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>

            {domain === "fleet" && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Matrícula da Viatura</label>
                <select
                  required
                  value={vehicleId}
                  onChange={e => setVehicleId(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white"
                >
                  <option value="" disabled>Selecione uma viatura...</option>
                  <option value="mat-01">MAT-01 (Volvo FH16)</option>
                  <option value="mat-02">MAT-02 (Mercedes Actros)</option>
                  <option value="mat-03">MAT-03 (Scania R450)</option>
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Descrição Detalhada</label>
              <textarea
                required
                rows={4}
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Descreva o problema com o máximo de detalhes possível..."
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Link
              href="/tarefas"
              className="px-4 py-2 text-slate-600 font-medium hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancelar
            </Link>
            <button
              type="submit"
              disabled={loading}
              className="flex items-center gap-2 bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-70"
            >
              <Save size={18} />
              {loading ? "A criar..." : "Criar Tarefa"}
            </button>
          </div>
        </form>
      </div>
    </SidebarLayout>
  );
}
