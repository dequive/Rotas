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
  vehicle_id: string;
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
      <div style={{ width: "100%" }}>
        {/* Back link */}
        <div style={{ marginBottom: 16 }}>
          <Link
            href="/viaturas"
            style={{
              fontSize: "13px",
              color: "var(--muted)",
              textDecoration: "none",
              fontFamily: "Manrope, sans-serif",
            }}
          >
            ← Viaturas
          </Link>
        </div>

        {/* Header */}
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
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-lg, 10px)",
            padding: 24,
            marginBottom: 20,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 16,
            }}
          >
            <h2
              style={{
                fontSize: "16px",
                fontWeight: 600,
                fontFamily: "Manrope, sans-serif",
                color: "var(--ink)",
              }}
            >
              Motoristas Atribuídos
              {assignmentList.length > 0 && (
                <span
                  style={{ marginLeft: 8, fontSize: "12px", fontWeight: 400, color: "var(--muted)" }}
                >
                  ({assignmentList.length})
                </span>
              )}
            </h2>
            <a
              href={`/viaturas/${id}/atribuir`}
              style={{
                padding: "5px 12px",
                border: "1px solid var(--border-strong)",
                borderRadius: "var(--r-md, 6px)",
                background: "var(--surface-2)",
                color: "var(--ink)",
                fontSize: "12px",
                fontWeight: 600,
                fontFamily: "Manrope, sans-serif",
                textDecoration: "none",
                display: "inline-block",
              }}
            >
              Atribuir Motorista
            </a>
          </div>

          {assignmentList.length === 0 ? (
            <p
              style={{
                fontSize: "13px",
                color: "var(--muted)",
                fontFamily: "Manrope, sans-serif",
              }}
            >
              Sem motoristas atribuídos a esta viatura.
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "13px",
                  fontFamily: "Manrope, sans-serif",
                }}
              >
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Motorista (ID)", "Tipo", "Atribuído em", "Encerrado em", "Estado"].map(
                      (h) => (
                        <th
                          key={h}
                          style={{
                            padding: "8px 12px",
                            textAlign: "left",
                            fontSize: "11px",
                            fontWeight: 600,
                            textTransform: "uppercase" as const,
                            letterSpacing: "0.05em",
                            color: "var(--muted)",
                          }}
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
                      <tr key={a.id} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td
                          style={{
                            padding: "10px 12px",
                            fontFamily: "IBM Plex Mono, monospace",
                            fontSize: "11px",
                            color: "var(--ink)",
                          }}
                        >
                          {a.driver_id}
                        </td>
                        <td
                          style={{
                            padding: "10px 12px",
                            fontSize: "12px",
                            color: "var(--muted)",
                          }}
                        >
                          {a.assignment_type ?? "—"}
                        </td>
                        <td
                          style={{
                            padding: "10px 12px",
                            fontFamily: "IBM Plex Mono, monospace",
                            fontSize: "12px",
                            color: "var(--ink)",
                          }}
                        >
                          {a.assigned_at ? a.assigned_at.slice(0, 10) : "—"}
                        </td>
                        <td
                          style={{
                            padding: "10px 12px",
                            fontFamily: "IBM Plex Mono, monospace",
                            fontSize: "12px",
                            color: "var(--muted)",
                          }}
                        >
                          {a.unassigned_at ? a.unassigned_at.slice(0, 10) : "Actual"}
                        </td>
                        <td style={{ padding: "10px 12px" }}>
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
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-lg, 10px)",
            padding: 24,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 16,
            }}
          >
            <h2
              style={{
                fontSize: "16px",
                fontWeight: 600,
                fontFamily: "Manrope, sans-serif",
                color: "var(--ink)",
              }}
            >
              Documentos Operacionais
              {documents.length > 0 && (
                <span
                  style={{ marginLeft: 8, fontSize: "12px", fontWeight: 400, color: "var(--muted)" }}
                >
                  ({documents.length})
                </span>
              )}
            </h2>
            <DocumentUploadModal subjectType="vehicle" subjectId={id} />
          </div>
          <OperationalDocumentsList documents={documents} />
        </div>

        {/* Seguros */}
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-lg, 10px)",
            padding: 24,
            marginTop: 20,
          }}
        >
          <InsuranceTab vehicleId={id} />
        </div>
      </div>
    </SidebarLayout>
  );
}
