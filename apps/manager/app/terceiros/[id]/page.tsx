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
import PayablesTab from "./PayablesTab";

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

        <Tabs defaultValue="info">
          <TabsList>
            <TabsTrigger value="info">Info</TabsTrigger>
            <TabsTrigger value="contactos">
              Contactos{contacts.length > 0 ? ` (${contacts.length})` : ""}
            </TabsTrigger>
            <TabsTrigger value="documentos">Documentos</TabsTrigger>
            <TabsTrigger value="conta">Conta Corrente</TabsTrigger>
            <TabsTrigger value="payables">Faturas & Pedidos</TabsTrigger>
            <TabsTrigger value="avaliacoes">
              Avalia&#231;&#245;es
              {evalsResult.evaluations.length > 0
                ? ` (${evalsResult.evaluations.length})`
                : ""}
            </TabsTrigger>
          </TabsList>

          {/* Tab: Info */}
          <TabsContent value="info">
            <div className="mt-4 bg-surface border border-border rounded-lg p-6">
              <h2 className="text-base font-semibold text-ink mb-4">Identidade</h2>
              <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-[13px]">
                <dt className="text-muted">NUIT / Tax ID</dt>
                <dd className="font-mono text-ink m-0">{party.tax_id ?? "—"}</dd>

                <dt className="text-muted">Sector</dt>
                <dd className="text-ink m-0">{party.sector ?? "—"}</dd>

                <dt className="text-muted">C&#243;digo de actividade</dt>
                <dd className="font-mono text-ink m-0">{party.activity_code ?? "—"}</dd>

                <dt className="text-muted">Roles</dt>
                <dd className="flex flex-wrap gap-1 m-0">
                  {party.roles?.map((r) => (
                    <span
                      key={r}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-surface-2 text-muted border border-border"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-muted flex-shrink-0" />
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
            <div className="mt-4 bg-surface border border-border rounded-lg p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-base font-semibold text-ink">Sub-contactos</h2>
                <a
                  href={`/terceiros/${id}/contactos/novo`}
                  className="inline-flex items-center h-8 px-3 rounded-md bg-amber text-white text-xs font-bold no-underline hover:bg-amber-dark transition-colors duration-100"
                >
                  Adicionar Contacto
                </a>
              </div>
              {contacts.length === 0 ? (
                <p className="text-[13px] text-muted">Sem contactos registados</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-[13px]">
                    <thead>
                      <tr className="border-b border-border">
                        {["Nome", "Função", "Telefone", "Email", "Principal"].map((h) => (
                          <th
                            key={h}
                            className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {contacts.map((c) => (
                        <tr key={c.id} className="border-b border-border">
                          <td className="px-3 py-2.5 font-semibold text-ink">{c.name}</td>
                          <td className="px-3 py-2.5 text-muted">{c.role ?? "—"}</td>
                          <td className="px-3 py-2.5 font-mono text-xs text-ink">
                            {c.phone ?? "—"}
                          </td>
                          <td className="px-3 py-2.5 text-xs text-ink">{c.email ?? "—"}</td>
                          <td className="px-3 py-2.5 text-amber">{c.is_primary ? "✓" : ""}</td>
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
            <div className="mt-4 bg-surface border border-border rounded-lg p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-base font-semibold text-ink">
                  Documentos Operacionais
                  {documents.length > 0 && (
                    <span className="ml-2 text-xs font-normal text-muted">
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

          {/* Tab: Faturas & Pedidos */}
          <TabsContent value="payables">
            <PayablesTab thirdPartyId={id} />
          </TabsContent>

          {/* Tab: Avaliações */}
          <TabsContent value="avaliacoes">
            <div className="mt-4 bg-surface border border-border rounded-lg p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-base font-semibold text-ink">
                    Avalia&#231;&#245;es de Fornecedor
                  </h2>
                  {evalsResult.average_score && (
                    <p className="text-[13px] text-muted mt-1">
                      Score m&#233;dio:{" "}
                      <span className="font-mono font-semibold text-ink">
                        {evalsResult.average_score}/10
                      </span>
                    </p>
                  )}
                </div>
                <a
                  href={`/terceiros/${id}/avaliacoes/nova`}
                  className="inline-flex items-center h-8 px-3 rounded-md bg-amber text-white text-xs font-bold no-underline hover:bg-amber-dark transition-colors duration-100"
                >
                  Nova Avalia&#231;&#227;o
                </a>
              </div>

              {evalsResult.evaluations.length === 0 ? (
                <p className="text-[13px] text-muted">Sem avalia&#231;&#245;es registadas</p>
              ) : (
                <div className="flex flex-col gap-4">
                  {evalsResult.evaluations.map((ev) => (
                    <div key={ev.id} className="border border-border rounded-lg p-4">
                      <div className="flex justify-between items-start mb-3">
                        <span className="font-mono text-xs text-muted">{ev.evaluation_date}</span>
                        <span className="font-mono text-2xl font-medium text-amber">
                          {parseFloat(ev.score).toFixed(1)}/10
                        </span>
                      </div>
                      {ev.notes && (
                        <p className="text-[13px] text-muted mb-3">{ev.notes}</p>
                      )}
                      <div className="grid grid-cols-3 gap-2">
                        {ev.criteria.map((c, i) => (
                          <div key={i} className="bg-surface-2 rounded-md px-2.5 py-2">
                            <p className="text-[11px] text-muted mb-0.5">{c.name}</p>
                            <p className="font-mono font-semibold text-[13px] text-ink">
                              {c.score}/10
                            </p>
                            <p className="text-[11px] text-muted">
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
