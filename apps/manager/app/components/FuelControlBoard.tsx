import { AlertTriangle, Fuel, Gauge, MapPin, ShoppingCart, Warehouse } from "lucide-react";

import type { FuelControlBoardLoadResult, FuelTank } from "../lib/fuel-operations-api";
import { KpiCard } from "@/app/components/ui/KpiCard";
import { MoneyCell } from "@/app/components/ui/MonoCell";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { EmptyStateInline } from "@/app/components/ui/EmptyState";
import { DataSourceBadge } from "@/app/components/ui/DataSourceBadge";
import { FuelPurchaseModal } from "@/app/components/FuelPurchaseModal";

interface FuelControlBoardProps {
  result: FuelControlBoardLoadResult;
}

export function FuelControlBoard({ result }: FuelControlBoardProps) {
  const { board } = result;

  return (
    <section className="mt-6" aria-labelledby="fuel-board-title">
      <PageHeader
        eyebrow="Combustível Interno"
        title="Fuel Control Board"
        description="Stock teórico por movimento, compras pendentes e risco de autonomia."
        actions={
          <div className="flex items-center gap-2.5">
            <DataSourceBadge source={result.source} message={result.message ?? undefined} />
            <FuelPurchaseModal />
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        <div className="fuel-main">
          <section
            className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4"
            aria-label="Indicadores de combustível"
          >
            <KpiCard
              icon={<Warehouse size={16} />}
              label="Tanques activos"
              value={board.summary.tanks}
              semantic="default"
            />
            <KpiCard
              icon={<Gauge size={16} />}
              label="Stock teórico"
              value={`${formatLiters(board.summary.totalStockLiters)} L`}
              semantic="default"
            />
            <KpiCard
              icon={<ShoppingCart size={16} />}
              label="Compras pendentes"
              value={board.summary.purchasesPending}
              semantic={board.summary.purchasesPending > 0 ? "warning" : "default"}
            />
            <KpiCard
              icon={<AlertTriangle size={16} />}
              label="Abaixo do mínimo"
              value={board.summary.lowStockTanks}
              semantic={board.summary.lowStockTanks > 0 ? "error" : "default"}
            />
          </section>

          <section className="tank-grid" aria-label="Tanques de combustível">
            {board.tanks.map((tank) => (
              <TankStatus key={tank.id} tank={tank} />
            ))}
          </section>
        </div>

        <aside className="fuel-risk-list" aria-label="Riscos de stock">
          <header>
            <span className="w-[30px] h-[30px] rounded-md inline-flex items-center justify-center flex-shrink-0 bg-warning-bg text-warning">
              <AlertTriangle size={16} />
            </span>
            <div>
              <h3>Reposição necessária</h3>
              <p>{board.queues.lowStockTanks.length} tanques</p>
            </div>
          </header>
          {board.queues.lowStockTanks.length === 0 ? (
            <EmptyStateInline label="Sem tanques abaixo do mínimo." />
          ) : null}
          {board.queues.lowStockTanks.map((tank) => (
            <div className="fuel-risk-item" key={tank.id}>
              <strong>{tank.code}</strong>
              <span>{tank.name}</span>
              <small>
                {formatLiters(tank.currentStockLiters)} L disponíveis · mínimo{" "}
                {formatLiters(tank.minimumStockLiters)} L
              </small>
            </div>
          ))}
        </aside>
      </div>
    </section>
  );
}

function TankStatus({ tank }: { tank: FuelTank }) {
  const percentage = Math.min(100, Math.max(0, (tank.currentStockLiters / tank.capacityLiters) * 100));
  const isLow = tank.currentStockLiters <= tank.minimumStockLiters;

  return (
    <article className="bg-surface border border-border rounded-lg p-4">
      <div className="tank-title">
        <div>
          <strong>{tank.code}</strong>
          <span>{tank.name}</span>
        </div>
        <StatusBadge status={isLow ? "alerta" : "em-rota"} label={isLow ? "Repor" : "Normal"} />
      </div>
      <div
        className="h-2 bg-border rounded-full overflow-hidden"
        aria-label={`${percentage.toFixed(0)} por cento disponível`}
      >
        <span
          className={`h-full ${isLow ? "bg-error" : "bg-success"} rounded-full block`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <dl>
        <div>
          <dt>Stock</dt>
          <dd>{formatLiters(tank.currentStockLiters)} L</dd>
        </div>
        <div>
          <dt>Capacidade</dt>
          <dd>{formatLiters(tank.capacityLiters)} L</dd>
        </div>
        <div>
          <dt>Custo médio</dt>
          <dd><MoneyCell value={tank.averageUnitCost} semantic="cost" />/L</dd>
        </div>
      </dl>
      <small>
        <MapPin size={13} />
        {tank.location ?? "Local não indicado"}
      </small>
    </article>
  );
}

function formatLiters(value: number) {
  return new Intl.NumberFormat("pt-MZ", { maximumFractionDigits: 0 }).format(value);
}
