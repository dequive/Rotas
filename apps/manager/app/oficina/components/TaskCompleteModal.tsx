"use client";

import { useEffect, useState } from "react";

import { Button } from "@/app/components/ui/Button";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

export function TaskCompleteModal({
  open,
  taskDescription,
  defaultMinutes,
  busy,
  onClose,
  onConfirm,
}: {
  open: boolean;
  taskDescription: string;
  defaultMinutes: number;
  busy: boolean;
  onClose: () => void;
  onConfirm: (minutes: number, notes: string) => void;
}) {
  const [minutes, setMinutes] = useState(defaultMinutes || 1);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!open) return;
    setMinutes(defaultMinutes || 1);
    setNotes("");
  }, [defaultMinutes, open]);

  return (
    <ModalDialog open={open} onClose={onClose} title="Concluir tarefa">
      <div className="space-y-4 px-6 pb-6 pt-4">
        <p className="text-sm font-medium text-ink">{taskDescription}</p>
        <div>
          <label
            htmlFor="task-actual-minutes"
            className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted"
          >
            Minutos efetivos *
          </label>
          <input
            id="task-actual-minutes"
            type="number"
            min={1}
            value={minutes}
            onChange={(event) => setMinutes(Number(event.target.value))}
            className="h-10 w-full rounded-[var(--r-md)] border border-border-strong bg-surface px-3 font-mono text-sm tabular-nums text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
          />
        </div>
        <div>
          <label
            htmlFor="task-completion-notes"
            className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted"
          >
            Evidência de conclusão
          </label>
          <textarea
            id="task-completion-notes"
            rows={3}
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
            variant="primary"
            loading={busy}
            disabled={minutes < 1}
            onClick={() => onConfirm(minutes, notes.trim())}
          >
            Registar conclusão
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}
