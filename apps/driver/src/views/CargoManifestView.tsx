import { Save } from "lucide-react";
import { useState } from "react";
import { db, makeLocalId, queueOperation } from "../db";

export function CargoManifestView({
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

    const localId = makeLocalId("cargo_manifest");
    await queueOperation({
      localId,
      operation: "create",
      entityType: "cargo_manifest",
      payload: {
        tripLocalId,
        manifestNumber: fd.get("manifest_number"),
        shipperName: fd.get("shipper_name"),
        recipientName: fd.get("recipient_name"),
        cargoDescription: fd.get("cargo_description"),
        cargoType: fd.get("cargo_type"),
        packageCount: fd.get("package_count") ? Number(fd.get("package_count")) : undefined,
        grossWeightKg: fd.get("gross_weight_kg") ? Number(fd.get("gross_weight_kg")) : undefined,
        origin: fd.get("origin"),
        destination: fd.get("destination"),
        clientCapturedAt: new Date().toISOString(),
      },
    });

    await db.cargoManifests.add({
      localId,
      tripLocalId,
      manifestNumber: String(fd.get("manifest_number") ?? ""),
      status: "local_only",
    });

    setLoading(false);
    setMessage("Manifesto guardado offline.");
    onSaved();
  }

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Manifesto de carga</h2>
        <span>Declaração de mercadoria</span>
      </div>
      <form className="trip-form" onSubmit={handleSubmit}>
        <label>
          Nº Manifesto
          <input name="manifest_number" required placeholder="MAN-2026-001" />
        </label>
        <label>
          Remetente
          <input name="shipper_name" required placeholder="Empresa origem" />
        </label>
        <label>
          Destinatário
          <input name="recipient_name" required placeholder="Empresa destino" />
        </label>
        <label>
          Descrição da carga
          <input name="cargo_description" required placeholder="Cimento ensacado 50kg" />
        </label>
        <label>
          Tipo de carga
          <select name="cargo_type">
            <option value="general">Geral</option>
            <option value="perishable">Perecível</option>
            <option value="dangerous">Perigoso</option>
            <option value="fragile">Frágil</option>
            <option value="manufactured">Manufaturado</option>
          </select>
        </label>
        <div className="form-row-2">
          <label>
            Nº de volumes
            <input name="package_count" type="number" min={1} placeholder="100" />
          </label>
          <label>
            Peso bruto (kg)
            <input name="gross_weight_kg" type="number" step="0.1" placeholder="5000" />
          </label>
        </div>
        <label>
          Origem
          <input name="origin" required placeholder="Maputo" />
        </label>
        <label>
          Destino
          <input name="destination" required placeholder="Beira" />
        </label>
        {message && <p className="form-status local_only">{message}</p>}
        <button className="primary-action" type="submit" disabled={loading}>
          <Save size={18} />
          {loading ? "A guardar..." : "Guardar Manifesto"}
        </button>
      </form>
    </section>
  );
}
