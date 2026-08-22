import { ArrowLeft, Camera, FileSignature, Gauge, UserRound } from "lucide-react";
import Link from "next/link";

import { SidebarLayout } from "../../../components/SidebarLayout";
import { PageHeader } from "../../../components/ui/PageHeader";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { requireSession } from "../../../lib/auth";
import { loadVehicles } from "../../../lib/vehicles-api";
import { loadReceptionDetailResult } from "../../../lib/workshop-api";
import { QuoteFormModal } from "../../components/QuoteFormModal";
import VehicleHistoryPanel from "../../components/VehicleHistoryPanel";

const secondaryAction =
  "inline-flex h-10 items-center justify-center gap-2 rounded-[var(--r-md)] border border-border bg-surface px-4 text-sm font-semibold text-ink shadow-design-sm transition-colors hover:border-border-strong hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2";

function DetailValue({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-medium text-ink">{children}</dd>
    </div>
  );
}

export default async function ReceptionDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ evidence_warning?: string }>;
}) {
  await requireSession();
  const { id } = await params;
  const { evidence_warning: evidenceWarning } = await searchParams;
  const [result, vehicles] = await Promise.all([
    loadReceptionDetailResult(id),
    loadVehicles(),
  ]);

  const vehicleOptions = vehicles.map((vehicle) => ({
    id: vehicle.id,
    plate: vehicle.plate,
    brand: vehicle.brand,
    model: vehicle.model,
  }));
  const detail = result.data;
  const vehicle = detail
    ? vehicles.find((item) => item.id === detail.vehicle_id)
    : null;

  return (
    <SidebarLayout active="recepcao">
      <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6">
        {!detail ? (
          <>
            <PageHeader
              eyebrow="Oficina Auto"
              title="Receção indisponível"
              description="Não foi possível obter a ficha pedida a partir da API."
              actions={
                <Link href="/oficina" className={secondaryAction}>
                  <ArrowLeft aria-hidden="true" className="h-4 w-4" />
                  Voltar à oficina
                </Link>
              }
            />
            <div
              role="alert"
              className="rounded-[var(--r-md)] border border-status-cancelled bg-status-cancelled-soft p-4 text-sm text-status-cancelled"
            >
              {result.error ?? "A receção não existe ou não está acessível neste tenant."}
            </div>
          </>
        ) : (
          <>
            <PageHeader
              eyebrow="Ficha de entrada"
              title={detail.reception_number}
              description={
                vehicle
                  ? `${vehicle.plate} · ${vehicle.brand} ${vehicle.model}`
                  : `Viatura ${detail.vehicle_id}`
              }
              meta={<StatusBadge status={detail.status} />}
              actions={
                <>
                  <Link href="/oficina" className={secondaryAction}>
                    <ArrowLeft aria-hidden="true" className="h-4 w-4" />
                    Voltar
                  </Link>
                  <QuoteFormModal
                    vehicleOptions={vehicleOptions}
                    initialVehicleId={detail.vehicle_id}
                    initialClientId={detail.client_id}
                    initialReceptionId={detail.id}
                    triggerLabel="Criar orçamento"
                  />
                </>
              }
            />

            {evidenceWarning && (
              <div
                role="alert"
                className="rounded-[var(--r-md)] border border-status-awaiting bg-status-awaiting-soft p-4 text-sm text-status-awaiting"
              >
                A receção foi criada, mas {evidenceWarning} fotografia(s) não
                puderam ser associadas. O registo operacional foi preservado;
                confirme os anexos antes de avançar.
              </div>
            )}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
              <div className="space-y-6">
                <section className="rounded-[var(--r-lg)] border border-border bg-surface p-4 shadow-card sm:p-6">
                  <div className="mb-5 flex items-center gap-2">
                    <Gauge aria-hidden="true" className="h-5 w-5 text-rotas-600" />
                    <h2 className="text-base font-semibold text-ink">
                      Dados da entrada
                    </h2>
                  </div>
                  <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
                    <DetailValue label="Data e hora">
                      {new Date(detail.received_at).toLocaleString("pt-MZ")}
                    </DetailValue>
                    <DetailValue label="Odómetro">
                      <span className="font-mono tabular-nums">
                        {detail.odometer_at_reception.toLocaleString("pt-MZ")} km
                      </span>
                    </DetailValue>
                    <DetailValue label="Combustível">
                      {detail.fuel_level || "Não registado"}
                    </DetailValue>
                    <DetailValue label="Conclusão estimada">
                      {detail.estimated_completion_at
                        ? new Date(detail.estimated_completion_at).toLocaleString("pt-MZ")
                        : "Não definida"}
                    </DetailValue>
                    <DetailValue label="Responsável pela receção">
                      {detail.received_by}
                    </DetailValue>
                    <DetailValue label="Assinatura do cliente">
                      {detail.client_signature_file_id ? (
                        <a
                          href={`/api/files/${detail.client_signature_file_id}/download`}
                          className="font-semibold text-rotas-600 underline-offset-4 hover:underline"
                        >
                          Consultar evidência
                        </a>
                      ) : (
                        "Não anexada"
                      )}
                    </DetailValue>
                  </dl>
                </section>

                <section className="rounded-[var(--r-lg)] border border-border bg-surface p-4 shadow-card sm:p-6">
                  <div className="mb-5 flex items-center gap-2">
                    <UserRound aria-hidden="true" className="h-5 w-5 text-rotas-600" />
                    <h2 className="text-base font-semibold text-ink">
                      Entrega e levantamento
                    </h2>
                  </div>
                  <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                    <DetailValue label="Entregue por">
                      {detail.delivered_by_name || "Não registado"}
                      {detail.delivered_by_phone && (
                        <span className="mt-0.5 block text-xs font-normal text-muted">
                          {detail.delivered_by_phone}
                        </span>
                      )}
                    </DetailValue>
                    <DetailValue label="Autorizado a levantar">
                      {detail.pickup_authorized_by_name || "Não registado"}
                      {detail.pickup_authorized_by_phone && (
                        <span className="mt-0.5 block text-xs font-normal text-muted">
                          {detail.pickup_authorized_by_phone}
                        </span>
                      )}
                    </DetailValue>
                    <DetailValue label="Objetos pessoais">
                      {detail.personal_items || "Nenhum objeto registado"}
                    </DetailValue>
                  </dl>
                </section>

                <section className="rounded-[var(--r-lg)] border border-border bg-surface p-4 shadow-card sm:p-6">
                  <div className="mb-4 flex items-center gap-2">
                    <FileSignature aria-hidden="true" className="h-5 w-5 text-rotas-600" />
                    <h2 className="text-base font-semibold text-ink">
                      Declarações de entrada
                    </h2>
                  </div>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="rounded-[var(--r-md)] border border-border bg-surface-2 p-4">
                      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
                        Sintomas reportados
                      </h3>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                        {detail.reported_issues || "Nenhum sintoma registado."}
                      </p>
                    </div>
                    <div className="rounded-[var(--r-md)] border border-border bg-surface-2 p-4">
                      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
                        Condição visual
                      </h3>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                        {detail.visual_condition || "Nenhuma observação registada."}
                      </p>
                    </div>
                  </div>
                </section>

                <section className="rounded-[var(--r-lg)] border border-border bg-surface p-4 shadow-card sm:p-6">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Camera aria-hidden="true" className="h-5 w-5 text-rotas-600" />
                      <h2 className="text-base font-semibold text-ink">
                        Evidências fotográficas
                      </h2>
                    </div>
                    <span className="font-mono text-xs tabular-nums text-muted">
                      {detail.photos.length}
                    </span>
                  </div>
                  <p className="mb-4 text-xs text-muted">
                    Evidências anexadas são tratadas como registos imutáveis.
                  </p>
                  {detail.photos.length === 0 ? (
                    <p className="rounded-[var(--r-md)] border border-dashed border-border p-6 text-center text-sm text-muted">
                      Nenhuma fotografia anexada a esta receção.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {detail.photos.map((photo, index) => (
                        <a
                          key={photo.id}
                          href={`/api/files/${photo.file_id}/download`}
                          className="min-h-11 rounded-[var(--r-md)] border border-border px-3 py-2 text-xs font-semibold text-rotas-600 hover:bg-rotas-50 dark:hover:bg-surface-2"
                        >
                          {photo.caption || `Fotografia ${index + 1}`}
                        </a>
                      ))}
                    </div>
                  )}
                </section>
              </div>

              <aside>
                <VehicleHistoryPanel vehicleId={detail.vehicle_id} />
              </aside>
            </div>
          </>
        )}
      </div>
    </SidebarLayout>
  );
}
