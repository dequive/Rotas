import { requireSession } from "@/app/lib/auth";
import {
  loadThirdParty,
  loadContacts,
  loadEvaluations,
  loadOperationalDocuments,
  type OperationalDocument,
} from "@/app/lib/third-party-api";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OperationalDocumentsList } from "@/app/components/OperationalDocumentsList";
import { DocumentUploadModal } from "@/app/components/DocumentUploadModal";
import { notFound } from "next/navigation";
import ContaCorrenteTab from "./ContaCorrenteTab";

export default async function TerceiroDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireSession();
  const { id } = await params;

  const [party, contacts, evalsResult, documents] = await Promise.all([
    loadThirdParty(id).catch(() => null),
    loadContacts(id).catch(() => []),
    loadEvaluations(id).catch(() => ({ average_score: null, evaluations: [] })),
    loadOperationalDocuments("third_party", id).catch(() => [] as OperationalDocument[]),
  ]);

  if (!party) notFound();

  return (
    <SidebarLayout active="terceiros">
      <div className="w-full space-y-6">
        {/* Header */}
        <PageHeader
          eyebrow="Terceiros"
          title={party.name}
          description={party.trade_name ?? undefined}
          actions={
            <div className="flex items-center gap-3">
              <StatusBadge
                status={
                  party.status === "active"
                    ? "activo"
                    : party.status === "suspended"
                      ? "pending"
                      : "inactivo"
                }
                label={
                  party.status === "active"
                    ? "Activo"
                    : party.status === "suspended"
                      ? "Suspenso"
                      : "Inactivo"
                }
              />
              {evalsResult.average_score && (
                <span className="font-mono text-[13px] text-muted">
                  Score: {evalsResult.average_score}/10
                </span>
              )}
              <a
                href={`/terceiros/${id}/editar`}
                className="inline-flex items-center px-3 py-1.5 text-xs font-semibold border border-border-strong rounded-md bg-surface-2 text-ink hover:bg-surface transition-colors duration-100 no-underline"
              >
                Editar
              </a>
            </div>
          }
        />

        {/* Tabs */}
        <Tabs defaultValue="info">
          <TabsList>
            <TabsTrigger value="info">Info</TabsTrigger>
            <TabsTrigger value="contactos">
              Contactos{contacts.length > 0 ? ` (${contacts.length})` : ""}
            </TabsTrigger>
            <TabsTrigger value="documentos">Documentos</TabsTrigger>
            <TabsTrigger value="conta">Conta Corrente</TabsTrigger>
            <TabsTrigger value="avaliacoes">
              Avalia&#231;&#245;es
              {evalsResult.evaluations.length > 0
                ? ` (${evalsResult.evaluations.length})`
                : ""}
            </TabsTrigger>
          </TabsList>

          {/* Tab: Info */}
          <TabsContent value="info">
            <div
              style={{
                marginTop: 16,
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: "var(--r-lg, 10px)",
                padding: 24,
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
                Identidade
              </h2>
              <dl
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "12px 32px",
                  fontSize: "13px",
                }}
              >
                <dt style={{ color: "var(--muted)", fontFamily: "Manrope, sans-serif" }}>
                  NUIT / Tax ID
                </dt>
                <dd
                  style={{
                    fontFamily: "IBM Plex Mono, monospace",
                    color: "var(--ink)",
                    margin: 0,
                  }}
                >
                  {party.tax_id ?? "—"}
                </dd>

                <dt style={{ color: "var(--muted)", fontFamily: "Manrope, sans-serif" }}>
                  Sector
                </dt>
                <dd style={{ color: "var(--ink)", fontFamily: "Manrope, sans-serif", margin: 0 }}>
                  {party.sector ?? "—"}
                </dd>

                <dt style={{ color: "var(--muted)", fontFamily: "Manrope, sans-serif" }}>
                  C&#243;digo de actividade
                </dt>
                <dd
                  style={{
                    fontFamily: "IBM Plex Mono, monospace",
                    color: "var(--ink)",
                    margin: 0,
                  }}
                >
                  {party.activity_code ?? "—"}
                </dd>

                <dt style={{ color: "var(--muted)", fontFamily: "Manrope, sans-serif" }}>
                  Roles
                </dt>
                <dd style={{ display: "flex", flexWrap: "wrap", gap: 4, margin: 0 }}>
                  {party.roles?.map((r) => (
                    <span
                      key={r}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "2px 8px",
                        borderRadius: 999,
                        fontSize: "11px",
                        fontWeight: 600,
                        background: "var(--surface-2)",
                        color: "var(--muted)",
                        border: "1px solid var(--border)",
                        fontFamily: "Manrope, sans-serif",
                      }}
                    >
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          background: "var(--muted)",
                          flexShrink: 0,
                        }}
                      />
                      {r === "supplier"
                        ? "Fornecedor"
                        : r === "service_provider"
                          ? "Prestador"
                          : r === "client"
                            ? "Cliente"
                            : r}
                    </span>
                  ))}
                </dd>
              </dl>
            </div>
          </TabsContent>

          {/* Tab: Contactos */}
          <TabsContent value="contactos">
            <div
              style={{
                marginTop: 16,
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
                  Sub-contactos
                </h2>
                <a
                  href={`/terceiros/${id}/contactos/novo`}
                  style={{
                    padding: "5px 12px",
                    background: "var(--amber)",
                    color: "#fff",
                    borderRadius: "var(--r-md, 6px)",
                    fontSize: "12px",
                    fontWeight: 600,
                    fontFamily: "Manrope, sans-serif",
                    textDecoration: "none",
                    display: "inline-block",
                  }}
                >
                  Adicionar Contacto
                </a>
              </div>
              {contacts.length === 0 ? (
                <p
                  style={{
                    fontSize: "13px",
                    color: "var(--muted)",
                    fontFamily: "Manrope, sans-serif",
                  }}
                >
                  Sem contactos registados
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
                        {["Nome", "Função", "Telefone", "Email", "Principal"].map(
                          (h) => (
                            <th
                              key={h}
                              style={{
                                padding: "8px 12px",
                                textAlign: "left",
                                fontSize: "11px",
                                fontWeight: 600,
                                textTransform: "uppercase",
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
                      {contacts.map((c) => (
                        <tr
                          key={c.id}
                          style={{ borderBottom: "1px solid var(--border)" }}
                        >
                          <td
                            style={{
                              padding: "10px 12px",
                              fontWeight: 600,
                              color: "var(--ink)",
                            }}
                          >
                            {c.name}
                          </td>
                          <td
                            style={{
                              padding: "10px 12px",
                              color: "var(--muted)",
                            }}
                          >
                            {c.role ?? "—"}
                          </td>
                          <td
                            style={{
                              padding: "10px 12px",
                              fontFamily: "IBM Plex Mono, monospace",
                              fontSize: "12px",
                              color: "var(--ink)",
                            }}
                          >
                            {c.phone ?? "—"}
                          </td>
                          <td
                            style={{
                              padding: "10px 12px",
                              fontSize: "12px",
                              color: "var(--ink)",
                            }}
                          >
                            {c.email ?? "—"}
                          </td>
                          <td style={{ padding: "10px 12px", color: "var(--amber)" }}>
                            {c.is_primary ? "✓" : ""}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Tab: Documentos */}
          <TabsContent value="documentos">
            <div
              style={{
                marginTop: 16,
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
                      style={{
                        marginLeft: 8,
                        fontSize: "12px",
                        fontWeight: 400,
                        color: "var(--muted)",
                      }}
                    >
                      ({documents.length})
                    </span>
                  )}
                </h2>
                <DocumentUploadModal subjectType="third_party" subjectId={id} />
              </div>
              <OperationalDocumentsList documents={documents} />
            </div>
          </TabsContent>

          {/* Tab: Conta Corrente */}
          <TabsContent value="conta">
            <ContaCorrenteTab thirdPartyId={id} />
          </TabsContent>

          {/* Tab: Avaliações */}
          <TabsContent value="avaliacoes">
            <div
              style={{
                marginTop: 16,
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
                  alignItems: "flex-start",
                  marginBottom: 16,
                }}
              >
                <div>
                  <h2
                    style={{
                      fontSize: "16px",
                      fontWeight: 600,
                      fontFamily: "Manrope, sans-serif",
                      color: "var(--ink)",
                    }}
                  >
                    Avalia&#231;&#245;es de Fornecedor
                  </h2>
                  {evalsResult.average_score && (
                    <p
                      style={{
                        fontSize: "13px",
                        color: "var(--muted)",
                        fontFamily: "Manrope, sans-serif",
                        marginTop: 4,
                      }}
                    >
                      Score m&#233;dio:{" "}
                      <span
                        style={{
                          fontFamily: "IBM Plex Mono, monospace",
                          fontWeight: 600,
                          color: "var(--ink)",
                        }}
                      >
                        {evalsResult.average_score}/10
                      </span>
                    </p>
                  )}
                </div>
                <a
                  href={`/terceiros/${id}/avaliacoes/nova`}
                  style={{
                    padding: "5px 12px",
                    background: "var(--amber)",
                    color: "#fff",
                    borderRadius: "var(--r-md, 6px)",
                    fontSize: "12px",
                    fontWeight: 600,
                    fontFamily: "Manrope, sans-serif",
                    textDecoration: "none",
                    display: "inline-block",
                  }}
                >
                  Nova Avalia&#231;&#227;o
                </a>
              </div>
              {evalsResult.evaluations.length === 0 ? (
                <p
                  style={{
                    fontSize: "13px",
                    color: "var(--muted)",
                    fontFamily: "Manrope, sans-serif",
                  }}
                >
                  Sem avalia&#231;&#245;es registadas
                </p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  {evalsResult.evaluations.map((ev) => (
                    <div
                      key={ev.id}
                      style={{
                        border: "1px solid var(--border)",
                        borderRadius: "var(--r-lg, 10px)",
                        padding: 16,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                          marginBottom: 12,
                        }}
                      >
                        <span
                          style={{
                            fontFamily: "IBM Plex Mono, monospace",
                            fontSize: "12px",
                            color: "var(--muted)",
                          }}
                        >
                          {ev.evaluation_date}
                        </span>
                        <span
                          style={{
                            fontFamily: "IBM Plex Mono, monospace",
                            fontSize: "22px",
                            fontWeight: 500,
                            color: "#f59e0b",
                          }}
                        >
                          {parseFloat(ev.score).toFixed(1)}/10
                        </span>
                      </div>
                      {ev.notes && (
                        <p
                          style={{
                            fontSize: "13px",
                            color: "var(--muted)",
                            fontFamily: "Manrope, sans-serif",
                            marginBottom: 12,
                          }}
                        >
                          {ev.notes}
                        </p>
                      )}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(3, 1fr)",
                          gap: 8,
                        }}
                      >
                        {ev.criteria.map((c, i) => (
                          <div
                            key={i}
                            style={{
                              background: "var(--surface-2)",
                              borderRadius: "var(--r-md, 6px)",
                              padding: "8px 10px",
                            }}
                          >
                            <p
                              style={{
                                fontSize: "11px",
                                color: "var(--muted)",
                                fontFamily: "Manrope, sans-serif",
                                marginBottom: 2,
                              }}
                            >
                              {c.name}
                            </p>
                            <p
                              style={{
                                fontFamily: "IBM Plex Mono, monospace",
                                fontWeight: 600,
                                fontSize: "13px",
                                color: "var(--ink)",
                              }}
                            >
                              {c.score}/10
                            </p>
                            <p
                              style={{
                                fontSize: "11px",
                                color: "var(--muted)",
                                fontFamily: "Manrope, sans-serif",
                              }}
                            >
                              peso: {(c.weight * 100).toFixed(0)}%
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </SidebarLayout>
  );
}
