"use client";

import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { OperationalDocumentsList } from "@/app/components/OperationalDocumentsList";
import { DocumentUploadModal } from "@/app/components/DocumentUploadModal";
import InsuranceTab from "./InsuranceTab";

export default function TabAdmin({ 
  vehicleId, 
  assignmentList, 
  documents 
}: { 
  vehicleId: string; 
  assignmentList: any[]; 
  documents: any[] 
}) {
  return (
    <div className="space-y-6">
      {/* Motoristas Atribuídos */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900">
            Histórico de Motoristas
            {assignmentList.length > 0 && (
              <span className="ml-2 text-sm font-medium text-slate-500">
                ({assignmentList.length})
              </span>
            )}
          </h2>
          <a
            href={`/viaturas/${vehicleId}/atribuir`}
            className="inline-flex items-center px-4 py-2 text-sm font-bold border border-slate-200 rounded-xl bg-slate-50 text-slate-900 hover:bg-slate-100 transition-colors duration-100 no-underline shadow-sm"
          >
            Atribuir Motorista
          </a>
        </div>

        {assignmentList.length === 0 ? (
          <p className="text-sm text-slate-500 py-4">
            Sem motoristas atribuídos a esta viatura.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-slate-200">
                  {["Motorista", "Tipo", "Atribuído em", "Encerrado em", "Estado"].map(
                    (h) => (
                      <th
                        key={h}
                        className="px-3 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-slate-500 bg-slate-50 first:rounded-tl-lg last:rounded-tr-lg"
                      >
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {assignmentList.map((a) => {
                  const isActive = !a.unassigned_at;
                  return (
                    <tr key={a.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/50">
                      <td className="px-3 py-4 text-sm font-bold text-slate-900">
                        {a.driver_name ?? a.driver_id.slice(0, 8)}
                      </td>
                      <td className="px-3 py-4 text-xs text-slate-500 font-medium">
                        {a.assignment_type ?? "—"}
                      </td>
                      <td className="px-3 py-4 text-xs text-slate-700 font-medium">
                        {a.assigned_at ? a.assigned_at.slice(0, 10) : "—"}
                      </td>
                      <td className="px-3 py-4 text-xs text-slate-500 font-medium">
                        {a.unassigned_at ? a.unassigned_at.slice(0, 10) : "Atual"}
                      </td>
                      <td className="px-3 py-4">
                        <StatusBadge
                          status={isActive ? "activo" : "inactivo"}
                          label={isActive ? "Activo" : "Encerrada"}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Documentos Operacionais */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900">
            Documentos Operacionais
            {documents.length > 0 && (
              <span className="ml-2 text-sm font-medium text-slate-500">
                ({documents.length})
              </span>
            )}
          </h2>
          <DocumentUploadModal subjectType="vehicle" subjectId={vehicleId} />
        </div>
        <div className="mt-2">
          <OperationalDocumentsList documents={documents} />
        </div>
      </div>

      {/* Seguros */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <InsuranceTab vehicleId={vehicleId} />
      </div>
    </div>
  );
}
