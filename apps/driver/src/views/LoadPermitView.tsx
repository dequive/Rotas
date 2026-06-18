import { Save } from "lucide-react";
import { useState } from "react";
import { db, makeLocalId, queueOperation } from "../db";

export function LoadPermitView({
  tripLocalId,
  onSaved,
}: {
  tripLocalId: string;
  onSaved: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    const fd = new FormData(e.currentTarget);

    const localId = makeLocalId("load_permit");
    await queueOperation({
      localId,
      operation: "create",
      entityType: "load_permit",
      payload: {
        tripLocalId,
        permitNumber: fd.get("permit_number"),
        clientName: fd.get("client_name"),
        district: fd.get("district"),
        origin: fd.get("origin"),
        destination: fd.get("destination"),
        validFrom: fd.get("valid_from"),
        validUntil: fd.get("valid_until"),
        legType: fd.get("leg_type"),
        loadState: fd.get("load_state"),
        clientCapturedAt: new Date().toISOString(),
      },
    });

    await db.loadPermits.add({
      localId,
      tripLocalId,
      permitNumber: String(fd.get("permit_number") ?? ""),
      status: "local_only",
    });

    setLoading(false);
    setMessage("Load Permit guardado offline.");
    onSaved();
  }

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Load Permit</h2>
        <span>Autorização de carga</span>
      </div>
      <form className="trip-form" onSubmit={handleSubmit}>
        <label>
          Nº Autorização
          <input name="permit_number" required placeholder="LP-2026-001" />
        </label>
        <label>
          Nome do cliente
          <input name="client_name" required placeholder="Cliente Industrial" />
        </label>
        <label>
          Distrito
          <input name="district" placeholder="Maputo" />
        </label>
        <label>
          Origem
          <input name="origin" required placeholder="Maputo" />
        </label>
        <label>
          Destino
          <input name="destination" required placeholder="Beira" />
        </label>
        <div className="form-row-2">
          <label>
            Válido de
            <input name="valid_from" type="date" required />
          </label>
          <label>
            Válido até
            <input name="valid_until" type="date" required />
          </label>
        </div>
        <label>
          Tipo de percurso
          <select name="leg_type">
            <option value="single">Ida</option>
            <option value="round">Ida e volta</option>
          </select>
        </label>
        <label>
          Estado de carga
          <select name="load_state">
            <option value="loaded">Carregado</option>
            <option value="empty">Vazio</option>
          </select>
        </label>
        {message && <p className="form-status local_only">{message}</p>}
        <button className="primary-action" type="submit" disabled={loading}>
          <Save size={18} />
          {loading ? "A guardar..." : "Guardar Load Permit"}
        </button>
      </form>
    </section>
  );
}
