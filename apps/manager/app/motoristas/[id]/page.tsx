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

  const labelStyle: React.CSSProperties = {
    fontSize: "11px",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    color: "var(--muted)",
    fontFamily: "Manrope, sans-serif",
  };

  const valueStyle: React.CSSProperties = {
    fontFamily: "IBM Plex Mono, monospace",
    fontSize: "13px",
    color: "var(--ink)",
    margin: 0,
  };

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
      <div style={{ width: "100%" }}>
        {/* Back link */}
        <div style={{ marginBottom: 16 }}>
          <Link
            href="/motoristas"
            style={{
              fontSize: "13px",
              color: "var(--muted)",
              textDecoration: "none",
              fontFamily: "Manrope, sans-serif",
            }}
          >
            &larr; Motoristas
          </Link>
        </div>

        {/* Header */}
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

        {/* Identity info */}
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-lg, 10px)",
            padding: 24,
            marginBottom: 20,
          }}
        >
          <h2
            style={{
              fontSize: "16px",
              fontWeight: 600,
              fontFamily: "Manrope, sans-serif",
              color: "var(--ink)",
              marginBottom: 16,
            }}
          >
            Identidade e Documentos
          </h2>
          <dl
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: "14px 32px",
              fontSize: "13px",
            }}
          >
            <div>
              <dt style={labelStyle}>Carta de Condução</dt>
              <dd style={valueStyle}>{driver.license_number || "—"}</dd>
              <dd
                style={{
                  ...valueStyle,
                  fontSize: "11px",
                  color: "var(--muted)",
                  marginTop: 2,
                  ...expiryColor(driver.license_valid_until),
                }}
              >
                Val.: {driver.license_valid_until?.slice(0, 10) ?? "—"}
              </dd>
            </div>
            <div>
              <dt style={labelStyle}>Passaporte</dt>
              <dd style={valueStyle}>{driver.passport_number ?? "—"}</dd>
              {driver.passport_valid_until && (
                <dd
                  style={{
                    ...valueStyle,
                    fontSize: "11px",
                    color: "var(--muted)",
                    marginTop: 2,
                    ...expiryColor(driver.passport_valid_until),
                  }}
                >
                  Val.: {driver.passport_valid_until.slice(0, 10)}
                </dd>
              )}
            </div>
            <div>
              <dt style={labelStyle}>B.I.</dt>
              <dd style={valueStyle}>{driver.bi_number ?? "—"}</dd>
              {driver.bi_valid_until && (
                <dd
                  style={{
                    ...valueStyle,
                    fontSize: "11px",
                    color: "var(--muted)",
                    marginTop: 2,
                    ...expiryColor(driver.bi_valid_until),
                  }}
                >
                  Val.: {driver.bi_valid_until.slice(0, 10)}
                </dd>
              )}
            </div>
            <div>
              <dt style={labelStyle}>Categoria</dt>
              <dd style={valueStyle}>{driver.license_category || "—"}</dd>
            </div>
            <div>
              <dt style={labelStyle}>Tipo de Emprego</dt>
              <dd style={{ ...valueStyle, fontFamily: "Manrope, sans-serif" }}>
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
              Viaturas Atribu&#237;das
              {assignmentList.length > 0 && (
                <span
                  style={{ marginLeft: 8, fontSize: "12px", fontWeight: 400, color: "var(--muted)" }}
                >
                  ({assignmentList.length})
                </span>
              )}
            </h2>
            <a
              href={`/motoristas/${id}/atribuir`}
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
              Atribuir Viatura
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
              Sem viaturas atribu&#237;das a este motorista.
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
                    {["Viatura (ID)", "Tipo", "Atribu&#237;do em", "Encerrado em", "Estado"].map(
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
                          dangerouslySetInnerHTML={{ __html: h }}
                        />
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
                          <Link
                            href={`/viaturas/${a.vehicle_id}`}
                            style={{
                              color: "var(--amber)",
                              textDecoration: "none",
                            }}
                          >
                            {a.vehicle_id}
                          </Link>
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
            <DocumentUploadModal subjectType="driver" subjectId={id} />
          </div>
          <OperationalDocumentsList documents={documents} />
        </div>
      </div>
    </SidebarLayout>
  );
}
