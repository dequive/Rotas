import { Route } from "lucide-react";
import { requireSession } from "../lib/auth";
import { loadKnownRoutes } from "../lib/known-routes-api";
import { loadDriverDespachoTable } from "../lib/operations-admin-api";
import { SidebarLayout } from "../components/SidebarLayout";
import { KnownRouteFormModal } from "../components/KnownRouteFormModal";
import { KnownRouteDeleteButton } from "../components/KnownRouteDeleteButton";
import { DriverDespachoTableAdmin } from "../components/DriverDespachoTableAdmin";
import { getApiConfig } from "../lib/billing-api";
import { StatusBadge } from "../components/ui/StatusBadge";
import { PageHeader } from "../components/ui/PageHeader";

function money(v: number | null) {
  if (v === null) return "-";
  return new Intl.NumberFormat("pt-MZ", { style: "currency", currency: "MZN", maximumFractionDigits: 0 }).format(v);
}

export default async function RotasConfigPage() {
  await requireSession();
  const [routes, despachoResult] = await Promise.all([
    loadKnownRoutes(),
    loadDriverDespachoTable(),
  ]);
  const apiConfig = getApiConfig();

  return (
    <SidebarLayout active="rotas-config">
      <PageHeader
        eyebrow="Config"
        title="Configuração de Rotas"
        description="Registe os destinos uma única vez. Ao criar uma viagem, a distância, o despacho e o combustível são preenchidos automaticamente."
        actions={<KnownRouteFormModal />}
      />

      {/* Catálogo de destinos */}
      <section className="bg-surface border border-border rounded-lg p-4 mb-6">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-base font-semibold m-0">Catálogo de destinos</h2>
          <span>{routes.length} rotas</span>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Origem</th>
                <th>Destino</th>
                <th>Distância</th>
                <th>Combustível</th>
                <th>Despacho vazio</th>
                <th>Despacho carregado</th>
                <th>Notas</th>
                <th>Acções</th>
              </tr>
            </thead>
            <tbody>
              {routes.length === 0 ? (
                <tr><td colSpan={7} className="text-muted text-center py-6">Sem rotas registadas. Adicione a primeira rota.</td></tr>
              ) : (
                routes.map((r) => {
                  const tier = despachoResult.table.tiers.find(
                    (t) => r.distance_km >= t.min_km && (t.max_km === null || r.distance_km < t.max_km)
                  );
                  return (
                    <tr key={r.id}>
                      <td><strong>{r.origin}</strong></td>
                      <td>
                        <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                          <Route size={14} />
                          {r.destination}
                        </span>
                      </td>
                      <td>{r.distance_km.toLocaleString("pt-MZ")} km</td>
                      <td>{r.avg_fuel_liters !== null ? `${r.avg_fuel_liters} L` : <span className="block mt-0.5 text-muted text-xs">Auto</span>}</td>
                      <td>
                        {r.despacho_vazio !== null ? (
                          <StatusBadge status="aguarda" label={money(r.despacho_vazio)} />
                        ) : tier ? (
                          <span className="block mt-0.5 text-muted text-xs"><span className="font-mono tabular-nums">{money(tier.amount)}</span> (faixa)</span>
                        ) : (
                          <StatusBadge status="alerta" label="Fora das faixas" />
                        )}
                      </td>
                      <td>
                        {r.despacho_carregado !== null ? (
                          <StatusBadge status="aguarda" label={money(r.despacho_carregado)} />
                        ) : tier ? (
                          <span className="block mt-0.5 text-muted text-xs"><span className="font-mono tabular-nums">{money(tier.amount)}</span> (faixa)</span>
                        ) : (
                          <StatusBadge status="alerta" label="Fora das faixas" />
                        )}
                      </td>
                      <td><span className="block mt-0.5 text-muted text-xs">{r.notes ?? "-"}</span></td>
                      <td className="flex items-center gap-1.5 whitespace-nowrap">
                        <KnownRouteFormModal route={r} />
                        <KnownRouteDeleteButton routeId={r.id} routeLabel={`${r.origin} → ${r.destination}`} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Tabela de despacho */}
      <DriverDespachoTableAdmin apiConfig={apiConfig} result={despachoResult} />
    </SidebarLayout>
  );
}
