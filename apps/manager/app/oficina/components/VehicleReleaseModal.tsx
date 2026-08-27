"use client";

import { useEffect, useState } from "react";

import { Button } from "@/app/components/ui/Button";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

import SignatureCanvas from "./SignatureCanvas";

export interface VehicleReleasePayload {
  odometer_at_release: number;
  condition_at_release: string;
  picked_up_by_name: string;
  picked_up_by_phone: string | null;
  override_unauthorized_pickup: boolean;
  override_reason: string | null;
  client_signature_file_id: string;
  release_type: "after_service";
  notes: string | null;
}

export function VehicleReleaseModal({
  open,
  minimumOdometer,
  busy,
  onClose,
  onConfirm,
}: {
  open: boolean;
  minimumOdometer: number;
  busy: boolean;
  onClose: () => void;
  onConfirm: (payload: VehicleReleasePayload) => void;
}) {
  const [odometer, setOdometer] = useState(minimumOdometer);
  const [condition, setCondition] = useState("");
  const [personName, setPersonName] = useState("");
  const [phone, setPhone] = useState("");
  const [overridePickup, setOverridePickup] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [notes, setNotes] = useState("");
  const [signatureFileId, setSignatureFileId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setOdometer(minimumOdometer);
    setCondition("");
    setPersonName("");
    setPhone("");
    setOverridePickup(false);
    setOverrideReason("");
    setNotes("");
    setSignatureFileId(null);
  }, [minimumOdometer, open]);

  const canConfirm =
    !busy &&
    odometer >= minimumOdometer &&
    condition.trim().length > 0 &&
    personName.trim().length > 0 &&
    Boolean(signatureFileId) &&
    (!overridePickup || overrideReason.trim().length > 0);

  return (
    <ModalDialog
      open={open}
      onClose={onClose}
      title="Confirmar entrega da viatura"
      className="modal-wide"
    >
      <div className="space-y-5 px-6 pb-6 pt-4">
        <div className="rounded-[var(--r-md)] border border-status-awaiting bg-status-awaiting-soft p-3 text-xs text-status-awaiting">
          A entrega é um ato auditado. Só conclua depois de confirmar a fatura
          emitida, a pessoa autorizada, a condição e a assinatura do cliente.
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="release-odometer"
              className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted"
            >
              Odómetro de saída *
            </label>
            <input
              id="release-odometer"
              type="number"
              min={minimumOdometer}
              value={odometer}
              onChange={(event) => setOdometer(Number(event.target.value))}
              className="h-10 w-full rounded-[var(--r-md)] border border-border-strong bg-surface px-3 font-mono text-sm tabular-nums text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
            />
          </div>
          <div>
            <label
              htmlFor="release-person"
              className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted"
            >
              Pessoa que levantou *
            </label>
            <input
              id="release-person"
              value={personName}
              onChange={(event) => setPersonName(event.target.value)}
              className="h-10 w-full rounded-[var(--r-md)] border border-border-strong bg-surface px-3 text-sm text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
            />
          </div>
          <div>
            <label
              htmlFor="release-phone"
              className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted"
            >
              Telefone
            </label>
            <input
              id="release-phone"
              type="tel"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              className="h-10 w-full rounded-[var(--r-md)] border border-border-strong bg-surface px-3 text-sm text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
            />
          </div>
          <div>
            <label
              htmlFor="release-condition"
              className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted"
            >
              Condição de saída *
            </label>
            <input
              id="release-condition"
              value={condition}
              onChange={(event) => setCondition(event.target.value)}
              className="h-10 w-full rounded-[var(--r-md)] border border-border-strong bg-surface px-3 text-sm text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
            />
          </div>
        </div>
        <label className="flex min-h-11 items-center gap-3 rounded-[var(--r-md)] border border-border p-3 text-sm text-ink">
          <input
            type="checkbox"
            checked={overridePickup}
            onChange={(event) => setOverridePickup(event.target.checked)}
          />
          A pessoa difere da autorizada e possuo validação excecional
        </label>
        {overridePickup && (
          <div>
            <label
              htmlFor="release-override-reason"
              className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted"
            >
              Motivo da exceção *
            </label>
            <textarea
              id="release-override-reason"
              rows={2}
              value={overrideReason}
              onChange={(event) => setOverrideReason(event.target.value)}
              className="w-full rounded-[var(--r-md)] border border-border-strong bg-surface px-3 py-2 text-sm text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
            />
          </div>
        )}
        <SignatureCanvas
          onSignatureCaptured={(fileId) => setSignatureFileId(fileId)}
          onSignatureCleared={() => setSignatureFileId(null)}
        />
        <div>
          <label
            htmlFor="release-notes"
            className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted"
          >
            Observações finais
          </label>
          <textarea
            id="release-notes"
            rows={2}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className="w-full rounded-[var(--r-md)] border border-border-strong bg-surface px-3 py-2 text-sm text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
          />
        </div>
        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button
            type="button"
            variant="accent"
            loading={busy}
            disabled={!canConfirm}
            onClick={() =>
              onConfirm({
                odometer_at_release: odometer,
                condition_at_release: condition.trim(),
                picked_up_by_name: personName.trim(),
                picked_up_by_phone: phone.trim() || null,
                override_unauthorized_pickup: overridePickup,
                override_reason: overridePickup ? overrideReason.trim() : null,
                client_signature_file_id: signatureFileId!,
                release_type: "after_service",
                notes: notes.trim() || null,
              })
            }
          >
            Confirmar entrega
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}
