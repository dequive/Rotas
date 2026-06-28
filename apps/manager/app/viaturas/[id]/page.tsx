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
import VehicleTabsClient from "./VehicleTabsClient";

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

        <VehicleTabsClient 
          vehicleId={id} 
          assignmentList={assignmentList} 
          documents={documents} 
        />
      </div>
    </SidebarLayout>
  );
}
