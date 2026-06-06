import { AlertTriangle, Fuel, Gauge, MapPin, ShoppingCart, Warehouse } from "lucide-react";

import type { FuelControlBoardLoadResult, FuelTank } from "../lib/fuel-operations-api";

interface FuelControlBoardProps {
  result: FuelControlBoardLoadResult;
}

export function FuelControlBoard({ result }: FuelControlBoardProps) {
  const { board } = result;

  return (
    <section className="domain-section" aria-labelledby="fuel-board-title">
      <div className="domain-heading">
        <div className="title">
          <span className="eyebrow">Combustível Interno</span>
          <h2 id="fuel-board-title">Fuel Control Board</h2>
          <p>Stock teórico por movimento, compras pendentes e risco de autonomia.</p>
        </div>
      </div>

      <div className={`data-source ${result.source}`}>
        <Fuel size={15} />
        <span>{result.source === "api" ? "Stock carregado da API ROTAS." : result.message}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        <div className="fuel-main">
          <section className="fuel-summary" aria-label="Indicadores de combustível">
            <FuelMetric icon={Warehouse} label="Tanques activos" value={`${board.summary.tanks}`} />
            <FuelMetric
              icon={Gauge}
              label="Stock teórico"
              value={`${formatLiters(board.summary.totalStockLiters)} L`}
            />
            <FuelMetric
              icon={ShoppingCart}
              label="Compras pendentes"
              value={`${board.summary.purchasesPending}`}
            />
            <FuelMetric
              alert={board.summary.lowStockTanks > 0}
              icon={AlertTriangle}
              label="Abaixo do mínimo"
              value={`${board.summary.lowStockTanks}`}
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
            <span className="queue-icon orange">
              <AlertTriangle size={16} />
            </span>
            <div>
              <h3>Reposição necessária</h3>
              <p>{board.queues.lowStockTanks.length} tanques</p>
            </div>
          </header>
          {board.queues.lowStockTanks.length === 0 ? (
            <p className="empty-state">Sem tanques abaixo do mínimo.</p>
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

interface FuelMetricProps {
  alert?: boolean;
  icon: typeof Fuel;
  label: string;
  value: string;
}

function FuelMetric({ alert = false, icon: Icon, label, value }: FuelMetricProps) {
  return (
    <article className={`bg-panel border border-line rounded-lg p-4 ${alert ? "alert" : ""}`}>
      <Icon size={17} />
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function TankStatus({ tank }: { tank: FuelTank }) {
  const percentage = Math.min(100, Math.max(0, (tank.currentStockLiters / tank.capacityLiters) * 100));
  const isLow = tank.currentStockLiters <= tank.minimumStockLiters;

  return (
    <article className="bg-panel border border-line rounded-lg p-4">
      <div className="tank-title">
        <div>
          <strong>{tank.code}</strong>
          <span>{tank.name}</span>
        </div>
        <span className={`badge ${isLow ? "orange" : "green"}`}>{isLow ? "Repor" : "Normal"}</span>
      </div>
      <div
        className="h-2 bg-line rounded-full overflow-hidden"
        aria-label={`${percentage.toFixed(0)} por cento disponível`}
      >
        <span
          className={`h-full ${isLow ? "bg-orange" : "bg-green"} rounded-full block`}
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
          <dd>{formatMoney(tank.averageUnitCost)}/L</dd>
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

function formatMoney(value: number) {
  return new Intl.NumberFormat("pt-MZ", {
    style: "currency",
    currency: "MZN",
    maximumFractionDigits: 2,
  }).format(value);
}
