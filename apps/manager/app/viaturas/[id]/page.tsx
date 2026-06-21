import Link from "next/link";
import { requireSession } from "@/app/lib/auth";
import { apiFetch } from "@/app/lib/api";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { OperationalDocumentsList } from "@/app/components/OperationalDocumentsList";
import { DocumentUploadModal } from "@/app/components/DocumentUploadModal";
import type { OperationalDocument } from "@/app/components/OperationalDocumentsList";
import { notFound } from "next/navigation";
import { PageHeader } from "@/app/components/ui/PageHeader";
import InsuranceTab from "./InsuranceTab";

interface Assignment {
  id: string;
  driver_id: string;
  driver_name: string | null;
  vehicle_id: string;
  vehicle_plate: string | null;
  assigned_at: string | null;
  unassigned_at: string | null;
  assignment_type: string | null;
  notes: string | null;
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function VehicleDetailPage({ params }: PageProps) {
  await requireSession();
  const { id } = await params;

  const [vehicle, assignmentsResult, documents] = await Promise.all([
    apiFetch<Record<string, unknown>>(`/api/v1/vehicles/${id}`).catch(() => null),
    apiFetch<{ items?: Assignment[] } | Assignment[]>(
      `/api/v1/third-party/driver-vehicle-assignments?vehicle_id=${id}&limit=50`,
    ).catch(() => ({ items: [] as Assignment[] })),
    apiFetch<OperationalDocument[]>(
      `/api/v1/third-party/documents?subject_type=vehicle&subject_id=${id}`,
    ).catch(() => [] as OperationalDocument[]),
  ]);

  if (!vehicle) notFound();

  const assignmentList: Assignment[] = Array.isArray(assignmentsResult)
    ? assignmentsResult
    : (assignmentsResult as { items?: Assignment[] }).items ?? [];

  const vehicleStatus = String(vehicle.status ?? "inactive");
  const vehicleStatusKey =
    vehicleStatus === "active"
      ? "activo"
      : vehicleStatus === "maintenance"
        ? "pending"
        : "inactivo";
  const vehicleStatusLabel =
    vehicleStatus === "active"
      ? "Activa"
      : vehicleStatus === "maintenance"
        ? "Manutenção"
        : "Inactiva";

  return (
    <SidebarLayout active="viaturas">
      <div className="w-full">
        <div className="mb-4">
          <Link href="/viaturas" className="text-[13px] text-muted no-underline hover:text-ink transition-colors">
            ← Viaturas
          </Link>
        </div>

        <PageHeader
          eyebrow="Viaturas"
          title={String(vehicle.plate ?? "")}
          description={[
            String(vehicle.brand ?? ""),
            String(vehicle.model ?? ""),
            vehicle.year ? String(vehicle.year) : "",
          ].filter(Boolean).join(" · ")}
          actions={
            <div className="flex items-center gap-2">
              <StatusBadge status={vehicleStatusKey} label={vehicleStatusLabel} />
              <Link
                href={`/viaturas/${id}/historico`}
                className="inline-flex items-center px-3 py-1.5 text-xs font-semibold border border-border-strong rounded-md bg-surface-2 text-ink hover:bg-surface transition-colors duration-100"
              >
                Ver Histórico
              </Link>
            </div>
          }
        />

        {/* Motoristas Atribuídos */}
        <div className="bg-surface border border-border rounded-lg p-6 mb-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-ink">
              Motoristas Atribuídos
              {assignmentList.length > 0 && (
                <span className="ml-2 text-xs font-normal text-muted">
                  ({assignmentList.length})
                </span>
              )}
            </h2>
            <a
              href={`/viaturas/${id}/atribuir`}
              className="inline-flex items-center px-3 py-1.5 text-xs font-semibold border border-border-strong rounded-md bg-surface-2 text-ink hover:bg-surface transition-colors duration-100 no-underline"
            >
              Atribuir Motorista
            </a>
          </div>

          {assignmentList.length === 0 ? (
            <p className="text-[13px] text-muted">
              Sem motoristas atribuídos a esta viatura.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px] border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    {["Motorista", "Tipo", "Atribuído em", "Encerrado em", "Estado"].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted"
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
                      <tr key={a.id} className="border-b border-border">
                        <td className="px-3 py-2.5 text-[13px] text-ink">
                          {a.driver_name ?? a.driver_id.slice(0, 8)}
                        </td>
                        <td className="px-3 py-2.5 text-xs text-muted">
                          {a.assignment_type ?? "—"}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-xs text-ink">
                          {a.assigned_at ? a.assigned_at.slice(0, 10) : "—"}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-xs text-muted">
                          {a.unassigned_at ? a.unassigned_at.slice(0, 10) : "Actual"}
                        </td>
                        <td className="px-3 py-2.5">
                          <StatusBadge
                            status={isActive ? "activo" : "inactivo"}
                            label={isActive ? "Activa" : "Encerrada"}
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
        <div className="bg-surface border border-border rounded-lg p-6 mb-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-ink">
              Documentos Operacionais
              {documents.length > 0 && (
                <span className="ml-2 text-xs font-normal text-muted">
                  ({documents.length})
                </span>
              )}
            </h2>
            <DocumentUploadModal subjectType="vehicle" subjectId={id} />
          </div>
          <OperationalDocumentsList documents={documents} />
        </div>

        {/* Seguros */}
        <div className="bg-surface border border-border rounded-lg p-6 mt-5">
          <InsuranceTab vehicleId={id} />
        </div>
      </div>
    </SidebarLayout>
  );
}
