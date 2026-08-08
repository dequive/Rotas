"use client";

import { useEffect, useState } from "react";
import { Clock, Package, TrendingUp, Truck, User } from "lucide-react";
import { loadDriverScorecard } from "../lib/drivers-client-api";
import type { ScorecardData } from "../lib/drivers-api";

interface DriverSlim {
  id: string;
  full_name: string;
}

interface Props {
  drivers: DriverSlim[];
}

// Tier to CSS badge class mapping (D-09 / UI-SPEC.md)
const TIER_BADGE: Record<string, { cls: string; label: string }> = {
  verde: { cls: "badge green", label: "Verde" },
  amarelo: { cls: "badge orange", label: "Amarelo" },
  vermelho: { cls: "badge red", label: "Vermelho" },
  insuficiente: { cls: "badge", label: "Dados insuficientes" },
};

function formatKm(km: number): string {
  return km.toLocaleString("pt-MZ") + " km";
}

export function DriverScorecardPanel({ drivers }: Props) {
  const [selectedId, setSelectedId] = useState<string>(drivers[0]?.id ?? "");
  const [scorecard, setScorecard] = useState<ScorecardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    setLoading(true);
    setError(false);
    loadDriverScorecard(selectedId).then((data) => {
      if (cancelled) return;
      setLoading(false);
      if (!data) {
        setError(true);
      } else {
        setScorecard(data);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  async function handleDriverChange(id: string) {
    setSelectedId(id);
    setScorecard(null);
  }

  const tier = scorecard ? (TIER_BADGE[scorecard.tier] ?? TIER_BADGE.insuficiente) : null;
  const isInsufficient = scorecard?.tier === "insuficiente";

  return (
    <section>
      <hr className="border-0 border-t border-border mt-6" />
      <div className="flex items-end justify-between gap-4 mb-3">
        <h2 className="m-0 mt-0.5 text-[21px]">Desempenho de Motoristas</h2>
        <p className="m-0 mt-1 text-muted">Últimos 30 dias · Score composto</p>
      </div>

      <div className="mb-4">
        <select
          aria-label="Seleccionar motorista"
          className="min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-[14px] text-ink w-full focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
          value={selectedId}
          onChange={(e) => handleDriverChange(e.target.value)}
        >
          {drivers.map((d) => (
            <option key={d.id} value={d.id}>
              {d.full_name}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p className="text-error text-xs font-bold [overflow-wrap:anywhere]">Erro ao carregar scorecard. Tente novamente.</p>
      )}

      {loading && !scorecard && (
        <div className="transport-kpis">
          {[...Array(5)].map((_, i) => (
            <div className="transport-kpi" key={i}>
              <span className="bg-surface-2 h-4 rounded block w-4/5 animate-pulse" />
              <span className="bg-surface-2 h-3 rounded block w-3/5 animate-pulse" />
              <span className="bg-surface-2 h-[21px] rounded block w-2/5 animate-pulse" />
            </div>
          ))}
        </div>
      )}

      {scorecard && (
        <div className="transport-kpis">
          {/* Summary card — composite score */}
          <div className="transport-kpi">
            <User className="text-ink-2" size={16} />
            <span>Score composto</span>
            {isInsufficient ? (
              <>
                <span className={tier?.cls ?? "badge"}>{tier?.label}</span>
                <small className="text-xs text-muted">
                  {scorecard.message ?? "Mínimo 3 viagens em 30 dias para score válido"}
                </small>
              </>
            ) : (
              <>
                <strong aria-label={`Score: ${scorecard.score} — ${tier?.label}`}>
                  {scorecard.score}
                </strong>
                <span aria-label={`Tier: ${tier?.label}`} className={tier?.cls ?? "badge"}>
                  {tier?.label}
                </span>
              </>
            )}
          </div>

          {/* Proof de entrega */}
          <div className="transport-kpi">
            <Package className="text-ink-2" size={16} />
            <span>Proof de entrega</span>
            <strong>{scorecard.metrics.delivery_rate.toFixed(1)}%</strong>
          </div>

          {/* Disciplina de sync */}
          <div className="transport-kpi">
            <TrendingUp className="text-ink-2" size={16} />
            <span>Disciplina de sync</span>
            <strong>{scorecard.metrics.sync_score.toFixed(1)}</strong>
          </div>

          {/* Quilómetros */}
          <div className="transport-kpi">
            <Truck className="text-ink-2" size={16} />
            <span>Quilómetros</span>
            <strong>{formatKm(scorecard.metrics.total_km)}</strong>
          </div>

          {/* Eficiência de paradas */}
          <div className="transport-kpi">
            <Clock className="text-ink-2" size={16} />
            <span>Eficiência de paradas</span>
            <strong>{scorecard.metrics.stop_score.toFixed(1)}</strong>
          </div>
        </div>
      )}
    </section>
  );
}
