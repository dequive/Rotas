import { SidebarLayout } from "../../components/SidebarLayout";
import { PageHeader } from "../../components/ui/PageHeader";
import { requireSession } from "../../lib/auth";
import { loadVehicles } from "../../lib/vehicles-api";
import {
  loadQuotesResult,
  loadReceptionDetailResult,
} from "../../lib/workshop-api";
import { QuoteFormModal } from "../components/QuoteFormModal";
import { QuoteMasterDetailClient } from "../components/QuoteMasterDetailClient";

export default async function WorkshopQuotesPage({
  searchParams,
}: {
  searchParams: Promise<{ reception_id?: string }>;
}) {
  await requireSession();
  const { reception_id: receptionId } = await searchParams;
  const [quotesResult, vehicles, receptionResult] = await Promise.all([
    loadQuotesResult(),
    loadVehicles(),
    receptionId
      ? loadReceptionDetailResult(receptionId)
      : Promise.resolve({ data: null, error: null }),
  ]);

  const vehicleOptions = vehicles.map((vehicle) => ({
    id: vehicle.id,
    plate: vehicle.plate,
    brand: vehicle.brand,
    model: vehicle.model,
  }));
  const reception = receptionResult.data;

  return (
    <SidebarLayout active="orcamentos">
      <div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
        <PageHeader
          eyebrow="Oficina Auto"
          title="Orçamentos"
          description="Aprovação comercial rastreável, documentos imutáveis e suplementos separados por ordem de serviço."
          actions={<QuoteFormModal vehicleOptions={vehicleOptions} />}
        />

        {quotesResult.error && (
          <div
            role="alert"
            className="rounded-[var(--r-md)] border border-status-cancelled bg-status-cancelled-soft p-4 text-sm text-status-cancelled"
          >
            <p className="font-semibold">Fonte de orçamentos indisponível</p>
            <p className="mt-1">{quotesResult.error}</p>
          </div>
        )}

        {receptionId && receptionResult.error && (
          <div
            role="alert"
            className="rounded-[var(--r-md)] border border-status-awaiting bg-status-awaiting-soft p-4 text-sm text-status-awaiting"
          >
            A receção indicada não pôde ser vinculada ao novo orçamento:{" "}
            {receptionResult.error}
          </div>
        )}

        {quotesResult.truncated && (
          <p className="rounded-[var(--r-md)] border border-border bg-surface-2 px-4 py-3 text-xs text-muted">
            Foram carregados os 200 orçamentos mais recentes. A paginação
            completa será tratada numa onda posterior.
          </p>
        )}

        <QuoteMasterDetailClient
          initialQuotes={quotesResult.data}
          vehicleOptions={vehicleOptions}
          initialReception={
            reception
              ? {
                  id: reception.id,
                  vehicleId: reception.vehicle_id,
                  clientId: reception.client_id,
                  number: reception.reception_number,
                }
              : null
          }
        />
      </div>
    </SidebarLayout>
  );
}
