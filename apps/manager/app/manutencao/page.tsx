import { Wrench, AlertTriangle, Play, ClipboardList } from "lucide-react";
import { requireSession } from "@/app/lib/auth";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { MaintenanceImminentPanel } from "@/app/components/MaintenanceImminentPanel";
import { loadImminentMaintenanceAlerts } from "@/app/lib/control-tower-api";
import { loadWorkOrders } from "@/app/lib/workshop-api";
import { loadVehicles } from "@/app/lib/vehicles-api";
import { KpiCard } from "@/app/components/ui/KpiCard";
import {
  DataTable,
  RotasTableHeader,
  RotasTableRow,
  RotasTableCell,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
} from "@/app/components/ui/DataTable";
import { StatusBadge } from "@/app/components/ui/StatusBadge";

export default async function ManutencaoPage() {
  await requireSession();

  // Load backend data concurrently
  const [imminentAlerts, workOrdersResult, vehicles] = await Promise.all([
    loadImminentMaintenanceAlerts(),
    loadWorkOrders(),
    loadVehicles(),
  ]);

  const { data: workOrders, truncated: workOrdersTruncated, error: workOrdersError } = workOrdersResult;

  // Create a plate mapping dictionary
  const vehiclePlateMap = new Map<string, string>();
  vehicles.forEach((v) => {
    vehiclePlateMap.set(v.id, v.plate);
  });

  // Calculate KPIs
  const totalOrders = workOrders.length;
  const inProgressOrders = new Set(
    workOrders.filter((wo) => wo.status === "in_progress").map((wo) => wo.vehicle_id)
  ).size;
  const imminentAlertsCount = imminentAlerts.length;
  const totalEstimatedCost = workOrders.reduce((sum, wo) => sum + (wo.estimated_cost ?? 0), 0);

  const formattedCost = new Intl.NumberFormat("pt-MZ", {
    style: "currency",
    currency: "MZN",
    minimumFractionDigits: 0,
  }).format(totalEstimatedCost);

  return (
    <SidebarLayout active="manutencao">
      <div className="w-full space-y-6">
        <PageHeader 
          title="Manutenção de Frota" 
          description="Acompanhamento de revisões, alertas preventivos e ordens de trabalho ativas."
        />

        {/* KPIs Section */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <KpiCard
            label="Ordens de Trabalho"
            value={totalOrders}
            icon={<ClipboardList size={18} />}
            semantic="info"
          />
          <KpiCard
            label="Viaturas em Oficina"
            value={inProgressOrders}
            icon={<Play size={18} />}
            semantic="amber"
          />
          <KpiCard
            label="Alertas Ativos"
            value={imminentAlertsCount}
            icon={<AlertTriangle size={18} />}
            semantic={imminentAlertsCount > 0 ? "error" : "success"}
          />
          <KpiCard
            label="Custo Estimado"
            value={formattedCost}
            icon={<Wrench size={18} />}
            semantic="default"
          />
        </div>

        {/* Imminent Alerts Panel */}
        <div>
          <MaintenanceImminentPanel alerts={imminentAlerts} />
        </div>

        {/* Work Orders Database Table */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted">
              Ordens de Trabalho e Intervenções
            </h3>
            {workOrdersTruncated && (
              <span className="text-xs text-warning font-semibold">
                A mostrar os primeiros 500 registos
              </span>
            )}
          </div>

          {workOrdersError && (
            <div className="p-3 bg-error-bg border border-error/30 rounded-md text-xs font-semibold text-error">
              {workOrdersError}
            </div>
          )}

          <DataTable isEmpty={workOrders.length === 0} emptyLabel={workOrdersError ? "Não foi possível carregar as ordens de trabalho." : "Nenhuma ordem de trabalho ativa encontrada."}>
            <TableHeader>
              <TableRow>
                <RotasTableHeader>Nº Ordem</RotasTableHeader>
                <RotasTableHeader>Viatura</RotasTableHeader>
                <RotasTableHeader>Trabalho Planeado / Diagnóstico</RotasTableHeader>
                <RotasTableHeader>Estado</RotasTableHeader>
                <RotasTableHeader className="text-right">Custo Est. (MT)</RotasTableHeader>
                <RotasTableHeader className="text-right">Custo Real (MT)</RotasTableHeader>
                <RotasTableHeader className="text-right">Atualizado Em</RotasTableHeader>
              </TableRow>
            </TableHeader>
            <TableBody>
              {workOrders.map((wo) => {
                const plate = vehiclePlateMap.get(wo.vehicle_id) ?? "Desconhecida";
                const formattedEst = wo.estimated_cost ? wo.estimated_cost.toLocaleString("pt-MZ") : "-";
                const formattedAct = wo.actual_cost ? wo.actual_cost.toLocaleString("pt-MZ") : "-";
                const updatedAtDate = new Date(wo.updated_at).toLocaleDateString("pt-MZ");

                return (
                  <RotasTableRow key={wo.id}>
                    <RotasTableCell className="font-mono font-medium">{wo.work_order_number}</RotasTableCell>
                    <RotasTableCell className="font-semibold">{plate}</RotasTableCell>
                    <RotasTableCell>
                      <div>
                        <div className="font-medium text-ink">{wo.planned_work}</div>
                        {wo.diagnosis && (
                          <div className="text-xs text-muted mt-0.5">{wo.diagnosis}</div>
                        )}
                      </div>
                    </RotasTableCell>
                    <RotasTableCell>
                      <StatusBadge status={wo.status} />
                    </RotasTableCell>
                    <RotasTableCell className="text-right font-mono tabular-nums">{formattedEst}</RotasTableCell>
                    <RotasTableCell className="text-right font-mono tabular-nums">{formattedAct}</RotasTableCell>
                    <RotasTableCell className="text-right text-muted">{updatedAtDate}</RotasTableCell>
                  </RotasTableRow>
                );
              })}
            </TableBody>
          </DataTable>
        </section>
      </div>
    </SidebarLayout>
  );
}
