"use client";

import { useEffect, useState } from "react";

import { Button } from "@/app/components/ui/Button";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

interface WorkOrderTransitionModalProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  requireNotes?: boolean;
  requestActualCost?: boolean;
  defaultActualCost?: number;
  busy: boolean;
  onClose: () => void;
  onConfirm: (notes: string, actualCost?: number) => void;
}

export function WorkOrderTransitionModal({
  open,
  title,
  description,
  confirmLabel,
  requireNotes = false,
  requestActualCost = false,
  defaultActualCost = 0,
  busy,
  onClose,
  onConfirm,
}: WorkOrderTransitionModalProps) {
  const [notes, setNotes] = useState("");
  const [actualCost, setActualCost] = useState(defaultActualCost);

  useEffect(() => {
    if (!open) return;
    setNotes("");
    setActualCost(defaultActualCost);
  }, [defaultActualCost, open]);

  const canConfirm =
    !busy &&
    (!requireNotes || notes.trim().length > 0) &&
    (!requestActualCost || actualCost >= 0);

  return (
    <ModalDialog open={open} onClose={onClose} title={title}>
      <div className="space-y-4 px-6 pb-6 pt-4">
        <p className="text-sm leading-relaxed text-muted">{description}</p>
        <div>
          <label
            htmlFor="transition-notes"
            className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted"
          >
            Notas {requireNotes ? "*" : ""}
          </label>
          <textarea
            id="transition-notes"
            rows={3}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className="w-full rounded-[var(--r-md)] border border-border-strong bg-surface px-3 py-2 text-sm text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
          />
        </div>
        {requestActualCost && (
          <div>
            <label
              htmlFor="transition-actual-cost"
              className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted"
            >
              Custo real reconciliado (MZN) *
            </label>
            <input
              id="transition-actual-cost"
              type="number"
              min={0}
              step="0.01"
              value={actualCost}
              onChange={(event) => setActualCost(Number(event.target.value))}
              className="h-10 w-full rounded-[var(--r-md)] border border-border-strong bg-surface px-3 font-mono text-sm tabular-nums text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
            />
          </div>
        )}
        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button
            type="button"
            variant="primary"
            loading={busy}
            disabled={!canConfirm}
            onClick={() => onConfirm(notes.trim(), actualCost)}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}
