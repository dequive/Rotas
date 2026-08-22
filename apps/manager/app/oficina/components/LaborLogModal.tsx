"use client";

import { useState, type FormEvent } from "react";

type TaskOption = { id: string; description: string };

export function LaborLogModal({
  open,
  tasks,
  defaultUserId,
  busy,
  onClose,
  onSubmit,
}: {
  open: boolean;
  tasks: TaskOption[];
  defaultUserId: string;
  busy: boolean;
  onClose: () => void;
  onSubmit: (taskId: string, userId: string, minutes: number) => void;
}) {
  const [taskId, setTaskId] = useState(tasks[0]?.id ?? "");
  const [userId, setUserId] = useState(defaultUserId);
  const [minutes, setMinutes] = useState(30);
  if (!open) return null;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (taskId && userId && minutes > 0) onSubmit(taskId, userId, minutes);
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" role="presentation">
      <form onSubmit={submit} className="w-full max-w-lg space-y-4 rounded-xl border border-border bg-card p-6 shadow-xl">
        <div>
          <h2 className="text-lg font-semibold">Registar mão-de-obra</h2>
          <p className="text-sm text-muted-foreground">A taxa vigente do mecânico será aplicada pelo backend.</p>
        </div>
        <label className="block space-y-1 text-sm">
          <span>Tarefa</span>
          <select className="w-full rounded-md border bg-background p-2" value={taskId} onChange={(e) => setTaskId(e.target.value)} required>
            {tasks.map((task) => <option key={task.id} value={task.id}>{task.description}</option>)}
          </select>
        </label>
        <label className="block space-y-1 text-sm">
          <span>ID do mecânico</span>
          <input className="w-full rounded-md border bg-background p-2 font-mono" value={userId} onChange={(e) => setUserId(e.target.value)} required />
        </label>
        <label className="block space-y-1 text-sm">
          <span>Minutos trabalhados</span>
          <input className="w-full rounded-md border bg-background p-2" type="number" min={1} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} required />
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-md border px-4 py-2 text-sm">Cancelar</button>
          <button disabled={busy} className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50">{busy ? "A registar…" : "Registar"}</button>
        </div>
      </form>
    </div>
  );
}
