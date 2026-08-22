"use client";

import { SidebarLayout } from "@/app/components/SidebarLayout";
import { ArrowLeft, Save, Building, Truck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { bffFetch } from "@/app/lib/bff";

interface VehicleOption {
  id: string;
  plate: string;
}

interface CaseTypeOption {
  code: string;
  name: string;
}

export default function NovaTarefaPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [domain, setDomain] = useState<"fleet" | "internal">("fleet");
  
  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  const [caseTypeCode, setCaseTypeCode] = useState("");
  const [vehicles, setVehicles] = useState<VehicleOption[]>([]);
  const [caseTypes, setCaseTypes] = useState<CaseTypeOption[]>([]);
  const [loadError, setLoadError] = useState("");
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      bffFetch<VehicleOption[]>("/api/vehicles?limit=200", {
        path: "/api/vehicles?limit=200",
      }),
      bffFetch<CaseTypeOption[]>("/api/governance/case-types", {
        path: "/api/governance/case-types",
      }),
    ])
      .then(([vehicleOptions, caseTypeOptions]) => {
        if (!active) return;
        setVehicles(vehicleOptions);
        setCaseTypes(caseTypeOptions);
        setCaseTypeCode(caseTypeOptions[0]?.code ?? "");
      })
      .catch(() => {
        if (active) setLoadError("Não foi possível carregar os dados necessários.");
      });
    return () => {
      active = false;
    };
  }, []);
  
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setSubmitError("");

    try {
      if (domain === "fleet") {
        await bffFetch("/api/v1/workshop/maintenance-requests", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            vehicle_id: vehicleId,
            description: `${title} — ${description}`,
            priority: "normal",
          })
        });
      } else {
        await bffFetch("/api/governance/cases", {
          path: "/api/governance/cases",
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            case_type_code: caseTypeCode,
            payload: { title, description },
          })
        });
      }

      router.push("/tarefas");
      router.refresh();
    } catch (error) {
      console.error("Failed to create task", error);
      setSubmitError("Não foi possível criar a tarefa. Confirme os dados e tente novamente.");
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
                domain === "fleet" ? "border-amber bg-amber-light/30 text-amber-dark font-semibold" : "border-slate-200 hover:border-slate-300 text-slate-600"
              }`}
            >
              <Truck size={32} className={domain === "fleet" ? "text-amber-dark" : "text-slate-400"} />
              <div className="text-center">
                <p className="font-semibold">Viatura / Oficina</p>
                <p className="text-xs opacity-80 mt-1">Avarias, reparações ou manutenções de frota</p>
              </div>
            </button>

            <button
              type="button"
              onClick={() => setDomain("internal")}
              className={`flex-1 p-4 rounded-xl border-2 flex flex-col items-center justify-center gap-3 transition-colors ${
                domain === "internal" ? "border-amber bg-amber-light/30 text-amber-dark font-semibold" : "border-slate-200 hover:border-slate-300 text-slate-600"
              }`}
            >
              <Building size={32} className={domain === "internal" ? "text-amber-dark" : "text-slate-400"} />
              <div className="text-center">
                <p className="font-semibold">Governance / Incidentes</p>
                <p className="text-xs opacity-80 mt-1">Casos governados pela taxonomia ativa do tenant</p>
              </div>
            </button>
          </div>

          <hr className="border-slate-100" />

          {/* Dynamic Form Fields */}
          <div className="flex flex-col gap-4">
            <div>
              <label htmlFor="task-title" className="block text-sm font-medium text-slate-700 mb-1">Título Resumido</label>
              <input
                id="task-title"
                required
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder={domain === "fleet" ? "Ex: Pneu furado na roda traseira direita" : "Ex: Ar condicionado da sala de reuniões avariado"}
                className="w-full px-3 py-2 border border-border-strong bg-surface text-ink rounded-lg focus:outline-none focus:ring-2 focus:ring-focus-soft focus:border-focus"
              />
            </div>

            {domain === "fleet" && (
              <div>
                <label htmlFor="task-vehicle" className="block text-sm font-medium text-slate-700 mb-1">Matrícula da Viatura</label>
                <select
                  id="task-vehicle"
                  required
                  value={vehicleId}
                  onChange={e => setVehicleId(e.target.value)}
                  className="w-full px-3 py-2 border border-border-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-focus-soft focus:border-focus bg-surface text-ink"
                >
                  <option value="" disabled>Selecione uma viatura...</option>
                  {vehicles.map((vehicle) => (
                    <option key={vehicle.id} value={vehicle.id}>{vehicle.plate}</option>
                  ))}
                </select>
              </div>
            )}

            {domain === "internal" && (
              <div>
                <label htmlFor="task-case-type" className="block text-sm font-medium text-slate-700 mb-1">Tipo de caso</label>
                <select
                  id="task-case-type"
                  required
                  value={caseTypeCode}
                  onChange={e => setCaseTypeCode(e.target.value)}
                  className="w-full px-3 py-2 border border-border-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-focus-soft focus:border-focus bg-surface text-ink"
                >
                  <option value="" disabled>Selecione um tipo de caso...</option>
                  {caseTypes.map((caseType) => (
                    <option key={caseType.code} value={caseType.code}>{caseType.name}</option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label htmlFor="task-description" className="block text-sm font-medium text-slate-700 mb-1">Descrição Detalhada</label>
              <textarea
                id="task-description"
                required
                rows={4}
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Descreva o problema com o máximo de detalhes possível..."
                className="w-full px-3 py-2 border border-border-strong bg-surface text-ink rounded-lg focus:outline-none focus:ring-2 focus:ring-focus-soft focus:border-focus resize-none"
              />
            </div>
          </div>

          {(loadError || submitError) && (
            <p role="alert" className="rounded-lg bg-error-bg p-3 text-sm text-error">
              {submitError || loadError}
            </p>
          )}

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
              disabled={loading || Boolean(loadError) || (domain === "fleet" ? !vehicleId : !caseTypeCode)}
              className="flex items-center gap-2 bg-amber text-ink px-6 py-2 rounded-lg font-semibold hover:bg-amber-dark transition-colors disabled:opacity-70"
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
