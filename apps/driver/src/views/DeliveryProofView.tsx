import { Camera, Save } from "lucide-react";
import { useState } from "react";
import { db, makeLocalId, queueOperation } from "../db";
import type { PhotoQueueItem } from "../db";

export function DeliveryProofView({
  tripLocalId,
  onSaved,
}: {
  tripLocalId: string;
  onSaved: () => void;
}) {
  const [photo, setPhoto] = useState<File | undefined>();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    const fd = new FormData(e.currentTarget);

    const localId = makeLocalId("delivery_proof");
    let deliveryFileLocalId: string | undefined;

    if (photo) {
      const photoLocalId = makeLocalId("photo");
      const photoItem: Omit<PhotoQueueItem, "id"> = {
        localId: photoLocalId,
        entityType: "delivery_proof",
        entityLocalId: localId,
        fieldKey: "delivery_file",
        blob: photo,
        fileType: "document",
        retryCount: 0,
        status: "local_only",
        createdAt: new Date().toISOString(),
      };
      await db.photoQueue.add(photoItem);
      deliveryFileLocalId = photoLocalId;
    }

    await queueOperation({
      localId,
      operation: "create",
      entityType: "delivery_proof",
      payload: {
        tripLocalId,
        deliveredAt: new Date().toISOString(),
        recipientName: fd.get("recipient_name"),
        documentNumber: fd.get("document_number"),
        notes: fd.get("notes"),
        deliveryFileLocalId,
        clientCapturedAt: new Date().toISOString(),
      },
    });

    await db.deliveryProofs.add({
      localId,
      tripLocalId,
      deliveredAt: new Date().toISOString(),
      status: "local_only",
    });

    setLoading(false);
    setMessage("Prova de entrega guardada offline. Vai sincronizar quando houver rede.");
    onSaved();
  }

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Prova de entrega</h2>
        <span>Guia de descarga</span>
      </div>
      <form className="trip-form" onSubmit={handleSubmit}>
        <label>
          Nome do receptor
          <input name="recipient_name" required placeholder="Nome completo" />
        </label>
        <label>
          Nº do documento
          <input name="document_number" placeholder="GD-2026-001" />
        </label>
        <label>
          Foto da guia de descarga
          <div className="photo-upload">
            <input
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(e) => setPhoto(e.target.files?.[0])}
            />
            {photo ? (
              <span className="photo-selected">
                <Camera size={14} /> {photo.name}
              </span>
            ) : (
              <span className="photo-hint">
                <Camera size={14} /> Tirar foto ou escolher ficheiro
              </span>
            )}
          </div>
        </label>
        <label>
          Notas
          <textarea name="notes" rows={2} placeholder="Observações sobre a entrega..." />
        </label>
        {message && <p className="form-status local_only">{message}</p>}
        <button className="primary-action" type="submit" disabled={loading}>
          <Save size={18} />
          {loading ? "A guardar..." : "Registar entrega"}
        </button>
      </form>
    </section>
  );
}
