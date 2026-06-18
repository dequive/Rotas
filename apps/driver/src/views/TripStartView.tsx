import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { createTrip, getAuth, getVehicles, type ActiveTrip, type Vehicle } from "../api";

export function TripStartView({ onTripCreated }: { onTripCreated: (trip: ActiveTrip) => void }) {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const auth = getAuth();

  useEffect(() => {
    getVehicles()
      .then(setVehicles)
      .catch(() => setVehicles([]));
  }, []);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!auth) return;
    setError(null);
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    try {
      const trip = await createTrip({
        vehicle_id: fd.get("vehicle_id") as string,
        driver_id: auth.driverId,
        origin: fd.get("origin") as string,
        destination: fd.get("destination") as string,
        cargo_type: (fd.get("cargo_type") as string) || undefined,
        load_state: (fd.get("load_state") as string) || undefined,
      });
      onTripCreated(trip);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar viagem.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel trip-start-panel">
      <div className="panel-title">
        <h2>Nova viagem</h2>
        <span>Preencha os dados de partida</span>
      </div>
      <form className="trip-form" onSubmit={handleSubmit}>
        <label>
          Viatura
          <select name="vehicle_id" required>
            <option value="">Seleccionar viatura...</option>
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>
                {v.plate} — {v.brand} {v.model}
              </option>
            ))}
          </select>
        </label>
        <label>
          Origem
          <input name="origin" required placeholder="Maputo" />
        </label>
        <label>
          Destino
          <input name="destination" required placeholder="Beira" />
        </label>
        <label>
          Tipo de carga
          <input name="cargo_type" placeholder="Cimento ensacado" />
        </label>
        <label>
          Estado de carga
          <select name="load_state">
            <option value="">Não definido</option>
            <option value="loaded_empty">Carregado / Vazio</option>
            <option value="loaded_loaded">Carregado / Carregado</option>
            <option value="empty_loaded">Vazio / Carregado</option>
            <option value="empty_empty">Vazio / Vazio</option>
          </select>
        </label>
        {error && <p className="form-status failed">{error}</p>}
        <button className="primary-action" type="submit" disabled={loading}>
          <ArrowRight size={18} />
          {loading ? "A criar viagem..." : "Iniciar viagem"}
        </button>
      </form>
    </section>
  );
}
