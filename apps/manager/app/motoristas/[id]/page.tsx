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

interface Assignment {
  id: string;
  driver_id: string;
  vehicle_id: string;
  assigned_at: string | null;
  unassigned_at: string | null;
  assignment_type: string | null;
  notes: string | null;
}

interface Driver {
  id: string;
  full_name: string;
  phone: string;
  email: string | null;
  license_number: string;
  license_category: string;
  license_valid_until: string;
  passport_number: string | null;
  passport_valid_until: string | null;
  bi_number: string | null;
  bi_valid_until: string | null;
  employment_type: string;
  status: string;
  score: number;
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function DriverDetailPage({ params }: PageProps) {
  await requireSession();
  const { id } = await params;

  const [driver, assignmentsResult, documents] = await Promise.all([
    apiFetch<Driver>(`/api/v1/drivers/${id}`).catch(() => null),
    apiFetch<{ items?: Assignment[] } | Assignment[]>(
      `/api/v1/third-party/driver-vehicle-assignments?driver_id=${id}&limit=50`,
    ).catch(() => ({ items: [] as Assignment[] })),
    apiFetch<OperationalDocument[]>(
      `/api/v1/third-party/documents?subject_type=driver&subject_id=${id}`,
    ).catch(() => [] as OperationalDocument[]),
  ]);

  if (!driver) notFound();

  const assignmentList: Assignment[] = Array.isArray(assignmentsResult)
    ? assignmentsResult
    : (assignmentsResult as { items?: Assignment[] }).items ?? [];

  const driverStatus = driver.status;
  const driverStatusKey =
    driverStatus === "active"
      ? "activo"
      : driverStatus === "suspended"
        ? "pending"
        : "inactivo";
  const driverStatusLabel =
    driverStatus === "active"
      ? "Activo"
      : driverStatus === "suspended"
        ? "Suspenso"
        : "Inactivo";

  function daysUntil(dateStr: string | null): number | null {
    if (!dateStr) return null;
    return Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86_400_000);
  }

  function expiryColor(dateStr: string | null): React.CSSProperties {
    const days = daysUntil(dateStr);
    if (days === null) return {};
    if (days < 0) return { color: "var(--error, #ef4444)", fontWeight: 600 };
    if (days <= 30) return { color: "var(--warning, #f59e0b)", fontWeight: 600 };
    return {};
  }

  return (
    <SidebarLayout active="motoristas">
      <div className="w-full">
        <div className="mb-4">
          <Link href="/motoristas" className="text-[13px] text-muted no-underline hover:text-ink transition-colors">
            &larr; Motoristas
          </Link>
        </div>

        <PageHeader
          eyebrow="Motoristas"
          title={driver.full_name}
          description={[driver.phone, driver.email].filter(Boolean).join(" · ")}
          actions={
            <div className="flex items-center gap-2">
              <StatusBadge status={driverStatusKey} label={driverStatusLabel} />
              {driver.score > 0 && (
                <span className="font-mono text-[13px] text-muted">
                  Score: {driver.score}
                </span>
              )}
            </div>
          }
        />

        {/* Identidade e Documentos */}
        <div className="bg-surface border border-border rounded-lg p-6 mb-5">
          <h2 className="text-base font-semibold text-ink mb-4">
            Identidade e Documentos
          </h2>
          <dl className="grid grid-cols-3 gap-x-8 gap-y-3.5 text-[13px]">
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">Carta de Condução</dt>
              <dd className="font-mono text-[13px] text-ink m-0">{driver.license_number || "—"}</dd>
              <dd
                className="font-mono text-[11px] text-muted m-0 mt-0.5"
                style={expiryColor(driver.license_valid_until)}
              >
                Val.: {driver.license_valid_until?.slice(0, 10) ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">Passaporte</dt>
              <dd className="font-mono text-[13px] text-ink m-0">{driver.passport_number ?? "—"}</dd>
              {driver.passport_valid_until && (
                <dd
                  className="font-mono text-[11px] text-muted m-0 mt-0.5"
                  style={expiryColor(driver.passport_valid_until)}
                >
                  Val.: {driver.passport_valid_until.slice(0, 10)}
                </dd>
              )}
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">B.I.</dt>
              <dd className="font-mono text-[13px] text-ink m-0">{driver.bi_number ?? "—"}</dd>
              {driver.bi_valid_until && (
                <dd
                  className="font-mono text-[11px] text-muted m-0 mt-0.5"
                  style={expiryColor(driver.bi_valid_until)}
                >
                  Val.: {driver.bi_valid_until.slice(0, 10)}
                </dd>
              )}
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">Categoria</dt>
              <dd className="font-mono text-[13px] text-ink m-0">{driver.license_category || "—"}</dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">Tipo de Emprego</dt>
              <dd className="text-[13px] text-ink m-0">
                {driver.employment_type === "permanent"
                  ? "Efectivo"
                  : driver.employment_type === "contract"
                    ? "Contrato"
                    : driver.employment_type === "casual"
                      ? "Casual"
                      : driver.employment_type || "—"}
              </dd>
            </div>
          </dl>
        </div>

        {/* Viaturas Atribuídas */}
        <div className="bg-surface border border-border rounded-lg p-6 mb-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-ink">
              Viaturas Atribu&#237;das
              {assignmentList.length > 0 && (
                <span className="ml-2 text-xs font-normal text-muted">
                  ({assignmentList.length})
                </span>
              )}
            </h2>
            <a
              href={`/motoristas/${id}/atribuir`}
              className="inline-flex items-center px-3 py-1.5 text-xs font-semibold border border-border-strong rounded-md bg-surface-2 text-ink hover:bg-surface transition-colors duration-100 no-underline"
            >
              Atribuir Viatura
            </a>
          </div>

          {assignmentList.length === 0 ? (
            <p className="text-[13px] text-muted">
              Sem viaturas atribu&#237;das a este motorista.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px] border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    {["Viatura (ID)", "Tipo", "Atribuído em", "Encerrado em", "Estado"].map(
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
                        <td className="px-3 py-2.5 font-mono text-[11px] text-ink">
                          <Link
                            href={`/viaturas/${a.vehicle_id}`}
                            className="text-amber no-underline hover:underline"
                          >
                            {a.vehicle_id}
                          </Link>
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
        <div className="bg-surface border border-border rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-ink">
              Documentos Operacionais
              {documents.length > 0 && (
                <span className="ml-2 text-xs font-normal text-muted">
                  ({documents.length})
                </span>
              )}
            </h2>
            <DocumentUploadModal subjectType="driver" subjectId={id} />
          </div>
          <OperationalDocumentsList documents={documents} />
        </div>
      </div>
    </SidebarLayout>
  );
}
