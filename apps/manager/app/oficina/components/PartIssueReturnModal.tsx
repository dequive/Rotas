"use client";

import { useEffect, useState, type FormEvent } from "react";

type PartOption = { inventory_id: string; sku: string; name: string; net_quantity: number; unit: string };

export function PartIssueReturnModal({
  open,
  mode,
  parts,
  busy,
  onClose,
  onSubmit,
}: {
  open: boolean;
  mode: "issue" | "return";
  parts: PartOption[];
  busy: boolean;
  onClose: () => void;
  onSubmit: (inventoryId: string, quantity: number, reason: string) => void;
}) {
  const [inventoryId, setInventoryId] = useState(parts[0]?.inventory_id ?? "");
  const [quantity, setQuantity] = useState(1);
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (open && !inventoryId && parts[0]) setInventoryId(parts[0].inventory_id);
  }, [inventoryId, open, parts]);
  if (!open) return null;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (inventoryId && quantity > 0 && (mode === "issue" || reason.trim())) {
      onSubmit(inventoryId, quantity, reason.trim());
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" role="presentation">
      <form onSubmit={submit} className="w-full max-w-lg space-y-4 rounded-xl border border-border bg-card p-6 shadow-xl">
        <div>
          <h2 className="text-lg font-semibold">{mode === "issue" ? "Entrega física de peça" : "Devolução ao armazém"}</h2>
          <p className="text-sm text-muted-foreground">{mode === "issue" ? "A entrega respeita a reserva aprovada e o lock de stock." : "A devolução não pode exceder o consumo líquido da OS."}</p>
        </div>
        <label className="block space-y-1 text-sm">
          <span>Peça / inventário</span>
          {parts.length ? (
            <select className="w-full rounded-md border bg-background p-2" value={inventoryId} onChange={(e) => setInventoryId(e.target.value)} required>
              {parts.map((part) => <option key={part.inventory_id} value={part.inventory_id}>{part.sku} — {part.name} ({part.net_quantity} {part.unit})</option>)}
            </select>
          ) : (
            <input className="w-full rounded-md border bg-background p-2 font-mono" placeholder="UUID do artigo reservado" value={inventoryId} onChange={(e) => setInventoryId(e.target.value)} required />
          )}
        </label>
        <label className="block space-y-1 text-sm">
          <span>Quantidade</span>
          <input className="w-full rounded-md border bg-background p-2" type="number" min="0.001" step="0.001" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} required />
        </label>
        <label className="block space-y-1 text-sm">
          <span>{mode === "return" ? "Motivo da devolução" : "Notas"}</span>
          <textarea className="w-full rounded-md border bg-background p-2" value={reason} onChange={(e) => setReason(e.target.value)} required={mode === "return"} />
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-md border px-4 py-2 text-sm">Cancelar</button>
          <button disabled={busy} className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50">{busy ? "A processar…" : "Confirmar"}</button>
        </div>
      </form>
    </div>
  );
}
