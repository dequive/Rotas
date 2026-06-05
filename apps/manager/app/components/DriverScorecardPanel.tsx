"use client";

import { useEffect, useState } from "react";
import { Clock, Package, TrendingUp, Truck, User } from "lucide-react";
import { type ScorecardData, loadDriverScorecard } from "../lib/drivers-api";

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
      <hr className="section-divider" />
      <div className="domain-heading">
        <h2>Desempenho de Motoristas</h2>
        <p>Últimos 30 dias · Score composto</p>
      </div>

      <div style={{ marginBottom: 16 }}>
        <select
          aria-label="Seleccionar motorista"
          className="form-select"
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
        <p className="error-text">Erro ao carregar scorecard. Tente novamente.</p>
      )}

      {loading && !scorecard && (
        <div className="transport-kpis">
          {[...Array(5)].map((_, i) => (
            <div className="transport-kpi" key={i}>
              <span
                style={{
                  background: "var(--line)",
                  height: 16,
                  borderRadius: 4,
                  display: "block",
                  width: "80%",
                }}
              />
              <span
                style={{
                  background: "var(--line)",
                  height: 12,
                  borderRadius: 4,
                  display: "block",
                  width: "60%",
                }}
              />
              <span
                style={{
                  background: "var(--line)",
                  height: 21,
                  borderRadius: 4,
                  display: "block",
                  width: "40%",
                }}
              />
            </div>
          ))}
        </div>
      )}

      {scorecard && (
        <div className="transport-kpis">
          {/* Summary card — composite score */}
          <div className="transport-kpi">
            <User color="var(--blue)" size={16} />
            <span>Score composto</span>
            {isInsufficient ? (
              <>
                <span className={tier?.cls ?? "badge"}>{tier?.label}</span>
                <small style={{ fontSize: 12, color: "var(--muted)" }}>
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
            <Package color="var(--blue)" size={16} />
            <span>Proof de entrega</span>
            <strong>{scorecard.metrics.delivery_rate.toFixed(1)}%</strong>
          </div>

          {/* Disciplina de sync */}
          <div className="transport-kpi">
            <TrendingUp color="var(--blue)" size={16} />
            <span>Disciplina de sync</span>
            <strong>{scorecard.metrics.sync_score.toFixed(1)}</strong>
          </div>

          {/* Quilómetros */}
          <div className="transport-kpi">
            <Truck color="var(--blue)" size={16} />
            <span>Quilómetros</span>
            <strong>{formatKm(scorecard.metrics.total_km)}</strong>
          </div>

          {/* Eficiência de paradas */}
          <div className="transport-kpi">
            <Clock color="var(--blue)" size={16} />
            <span>Eficiência de paradas</span>
            <strong>{scorecard.metrics.stop_score.toFixed(1)}</strong>
          </div>
        </div>
      )}
    </section>
  );
}
