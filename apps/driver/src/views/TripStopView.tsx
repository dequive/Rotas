import { MapPin, Save } from "lucide-react";
import { useState } from "react";
import { makeLocalId, queueOperation } from "../db";

export function TripStopView({
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

    await queueOperation({
      localId: makeLocalId("trip_stop"),
      operation: "create",
      entityType: "trip_stop",
      payload: {
        tripLocalId,
        stopType: fd.get("stop_type"),
        location: fd.get("location"),
        notes: fd.get("notes"),
        durationMinutes: fd.get("duration_minutes") ? Number(fd.get("duration_minutes")) : undefined,
        clientCapturedAt: new Date().toISOString(),
      },
    });

    setLoading(false);
    setMessage("Paragem registada offline.");
    onSaved();
  }

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Registar paragem</h2>
        <span>Paragem durante a viagem</span>
      </div>
      <form className="trip-form" onSubmit={handleSubmit}>
        <label>
          Tipo de paragem
          <select name="stop_type" required>
            <option value="fuel">Abastecimento</option>
            <option value="meal">Refeição</option>
            <option value="rest">Descanso</option>
            <option value="breakdown">Avaria</option>
            <option value="police">Controlo policial</option>
            <option value="customs">Alfândega</option>
            <option value="other">Outro</option>
          </select>
        </label>
        <label>
          Localização
          <input name="location" placeholder="Nome do local / cidade" />
        </label>
        <label>
          Duração (minutos)
          <input name="duration_minutes" type="number" min={1} placeholder="30" />
        </label>
        <label>
          Notas
          <textarea name="notes" rows={2} placeholder="Observações sobre a paragem..." />
        </label>
        {message && <p className="form-status local_only">{message}</p>}
        <button className="primary-action" type="submit" disabled={loading}>
          <MapPin size={18} />
          {loading ? "A guardar..." : "Registar paragem"}
        </button>
      </form>
    </section>
  );
}
