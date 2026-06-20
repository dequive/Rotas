import { requireSession } from "@/app/lib/auth";
import {
  loadThirdParty,
  loadContacts,
  loadSupplierAccount,
  loadEvaluations,
} from "@/app/lib/third-party-api";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { notFound } from "next/navigation";

export default async function TerceiroDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireSession();
  const { id } = await params;

  const [party, contacts, account, evalsResult] = await Promise.all([
    loadThirdParty(id).catch(() => null),
    loadContacts(id).catch(() => []),
    loadSupplierAccount(id).catch(() => null),
    loadEvaluations(id).catch(() => ({ average_score: null, evaluations: [] })),
  ]);

  if (!party) notFound();

  const balance = account?.balance ?? "0.00";
  const balanceNum = parseFloat(balance);

  return (
    <SidebarLayout active="terceiros">
      <div className="w-full space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1
              className="text-2xl font-bold"
              style={{ fontFamily: "Manrope, sans-serif" }}
            >
              {party.name}
            </h1>
            {party.trade_name && (
              <p
                className="text-sm"
                style={{ color: "var(--muted)", marginTop: 2 }}
              >
                {party.trade_name}
              </p>
            )}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                marginTop: 8,
              }}
            >
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
                <span
                  style={{
                    fontSize: "13px",
                    color: "var(--muted)",
                    fontFamily: "IBM Plex Mono, monospace",
                  }}
                >
                  Score: {evalsResult.average_score}/10
                </span>
              )}
            </div>
          </div>
          <a
            href={`/terceiros/${id}/editar`}
            style={{
              padding: "7px 14px",
              border: "1px solid var(--border-strong)",
              borderRadius: "var(--r-md, 6px)",
              background: "var(--surface-2)",
              color: "var(--ink)",
              fontSize: "13px",
              fontWeight: 600,
              fontFamily: "Manrope, sans-serif",
              textDecoration: "none",
              display: "inline-block",
            }}
          >
            Editar
          </a>
        </div>

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
                </h2>
                <a
                  href={`/terceiros/${id}/documentos/upload`}
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
                  Upload Documento
                </a>
              </div>
              <p
                style={{
                  fontSize: "13px",
                  color: "var(--muted)",
                  fontFamily: "Manrope, sans-serif",
                }}
              >
                Documentos associados a este terceiro aparecem aqui.
              </p>
            </div>
          </TabsContent>

          {/* Tab: Conta Corrente */}
          <TabsContent value="conta">
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
                Conta Corrente
              </h2>
              {account ? (
                <>
                  {/* Balance hero */}
                  <div
                    style={{
                      textAlign: "center",
                      padding: "24px 16px",
                      marginBottom: 24,
                      borderRadius: "var(--r-lg, 10px)",
                      background:
                        balanceNum >= 0
                          ? "rgba(34,197,94,0.08)"
                          : "rgba(239,68,68,0.08)",
                    }}
                  >
                    <p
                      style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        color: "var(--muted)",
                        marginBottom: 4,
                        fontFamily: "Manrope, sans-serif",
                      }}
                    >
                      SALDO
                    </p>
                    <p
                      style={{
                        fontFamily: "IBM Plex Mono, monospace",
                        fontSize: "36px",
                        fontWeight: 500,
                        color: balanceNum >= 0 ? "var(--success, #22c55e)" : "var(--error, #ef4444)",
                        margin: 0,
                      }}
                    >
                      {balanceNum >= 0 ? "+" : ""}
                      {balanceNum.toLocaleString("pt-MZ", {
                        style: "currency",
                        currency: "MZN",
                      })}
                    </p>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "center",
                        gap: 32,
                        marginTop: 12,
                        fontSize: "13px",
                        color: "var(--muted)",
                        fontFamily: "Manrope, sans-serif",
                      }}
                    >
                      <span>
                        D&#233;bitos:{" "}
                        <span
                          style={{
                            fontFamily: "IBM Plex Mono, monospace",
                            color: "var(--ink)",
                          }}
                        >
                          {parseFloat(account.total_debits).toLocaleString("pt-MZ", {
                            style: "currency",
                            currency: "MZN",
                          })}
                        </span>
                      </span>
                      <span>
                        Cr&#233;ditos:{" "}
                        <span
                          style={{
                            fontFamily: "IBM Plex Mono, monospace",
                            color: "var(--ink)",
                          }}
                        >
                          {parseFloat(account.total_credits).toLocaleString("pt-MZ", {
                            style: "currency",
                            currency: "MZN",
                          })}
                        </span>
                      </span>
                    </div>
                  </div>

                  {/* Movements table */}
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
                          {["Data", "Tipo", "Origem", "Descrição", "Valor"].map(
                            (h, i) => (
                              <th
                                key={h}
                                style={{
                                  padding: "8px 12px",
                                  textAlign: i === 4 ? "right" : "left",
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
                        {account.entries.map((e) => (
                          <tr
                            key={e.id}
                            style={{ borderBottom: "1px solid var(--border)" }}
                          >
                            <td
                              style={{
                                padding: "10px 12px",
                                fontFamily: "IBM Plex Mono, monospace",
                                fontSize: "12px",
                                color: "var(--ink)",
                              }}
                            >
                              {e.entry_date}
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <span
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 4,
                                  padding: "2px 8px",
                                  borderRadius: 999,
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  background:
                                    e.entry_type === "credit"
                                      ? "rgba(34,197,94,0.10)"
                                      : "rgba(239,68,68,0.10)",
                                  color:
                                    e.entry_type === "credit"
                                      ? "var(--success, #22c55e)"
                                      : "var(--error, #ef4444)",
                                  fontFamily: "Manrope, sans-serif",
                                }}
                              >
                                <span
                                  style={{
                                    width: 6,
                                    height: 6,
                                    borderRadius: "50%",
                                    background:
                                      e.entry_type === "credit"
                                        ? "var(--success, #22c55e)"
                                        : "var(--error, #ef4444)",
                                    flexShrink: 0,
                                  }}
                                />
                                {e.entry_type === "credit" ? "Crédito" : "Débito"}
                              </span>
                            </td>
                            <td
                              style={{
                                padding: "10px 12px",
                                color: "var(--muted)",
                                fontSize: "12px",
                              }}
                            >
                              {e.source_type}
                            </td>
                            <td
                              style={{
                                padding: "10px 12px",
                                fontSize: "13px",
                                color: "var(--ink)",
                              }}
                            >
                              {e.description ?? "—"}
                            </td>
                            <td
                              style={{
                                padding: "10px 12px",
                                textAlign: "right",
                                fontFamily: "IBM Plex Mono, monospace",
                                fontWeight: 600,
                                fontSize: "13px",
                                color:
                                  e.entry_type === "credit"
                                    ? "var(--success, #22c55e)"
                                    : "var(--error, #ef4444)",
                              }}
                            >
                              {e.entry_type === "credit" ? "+" : "-"}
                              {parseFloat(e.amount).toLocaleString("pt-MZ", {
                                style: "currency",
                                currency: "MZN",
                              })}
                            </td>
                          </tr>
                        ))}
                        {account.entries.length === 0 && (
                          <tr>
                            <td
                              colSpan={5}
                              style={{
                                padding: "32px 12px",
                                textAlign: "center",
                                color: "var(--muted)",
                                fontSize: "13px",
                                fontFamily: "Manrope, sans-serif",
                              }}
                            >
                              Sem movimentos registados
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <p
                  style={{
                    fontSize: "13px",
                    color: "var(--muted)",
                    fontFamily: "Manrope, sans-serif",
                  }}
                >
                  Conta corrente n&#227;o dispon&#237;vel
                </p>
              )}
            </div>
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
