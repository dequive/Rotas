"use client";

import { CheckCircle, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Trip } from "../lib/trips-api";

const btnBase = "inline-flex items-center gap-1 h-[30px] px-2.5 bg-surface text-ink border border-border rounded-md text-xs font-bold whitespace-nowrap cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed";
const btnGreen = "text-success bg-success-bg border-success-border";
const btnCyan = "text-info bg-info-bg border-info-border";
const errorCls = "text-error text-[13px] m-0 bg-error-bg border border-error-border rounded-md px-3 py-2";

export function TripActionButton({ trip }: { trip: Trip }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showComplete, setShowComplete] = useState(false);
  const [showStart, setShowStart] = useState(false);
  const [kmStart, setKmStart] = useState("");
  const [kmEnd, setKmEnd] = useState("");

  async function runAction(body: Record<string, unknown>, fallbackMessage: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/trips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const body = (await res.json()) as { detail?: string; error?: { message?: string; code?: string } };
        throw new Error(body.error?.message ?? body.error?.code ?? body.detail ?? fallbackMessage);
      }
      router.refresh();
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : fallbackMessage);
      return false;
    } finally {
      setLoading(false);
    }
  }

  async function handleRequestClearance() {
    await runAction(
      { _action: "request_clearance", id: trip.id },
      "Erro ao solicitar autorização de saída.",
    );
  }

  async function handleStart(e: React.FormEvent) {
    e.preventDefault();
    const parsedKm = Number(kmStart);
    if (!Number.isFinite(parsedKm) || parsedKm < 0) {
      setError("Informe uma quilometragem inicial válida.");
      return;
    }
    const started = await runAction(
      { _action: "start", id: trip.id, km_start: parsedKm },
      "Erro ao iniciar viagem.",
    );
    if (started) setShowStart(false);
  }

  async function handleComplete(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/trips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ _action: "complete", id: trip.id, km_end: Number(kmEnd) }),
      });
      if (!res.ok) {
        const body = (await res.json()) as { detail?: string; error?: { message?: string; code?: string } };
        setError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao concluir viagem.");
        return;
      }
      setShowComplete(false);
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  if (trip.status === "planned") {
    return (
      <div>
        <button className={`${btnBase} ${btnCyan}`} onClick={handleRequestClearance} disabled={loading} title="Solicitar autorização de saída">
          <Play size={14} />
          {loading ? "..." : "Solicitar saída"}
        </button>
        {error && <p className={errorCls}>{error}</p>}
      </div>
    );
  }

  if (trip.status === "dispatch_pending") {
    return <span className="text-xs font-semibold text-warning">Aguarda autorização</span>;
  }

  if (trip.status === "dispatched") {
    if (!showStart) {
      return (
        <button className={`${btnBase} ${btnGreen}`} onClick={() => setShowStart(true)} title="Iniciar viagem">
          <Play size={14} /> Iniciar
        </button>
      );
    }
    return (
      <form onSubmit={handleStart} className="flex items-center gap-1.5">
        <label className="sr-only" htmlFor={`km-start-${trip.id}`}>Km inicial</label>
        <input
          id={`km-start-${trip.id}`}
          type="number"
          value={kmStart}
          onChange={(e) => setKmStart(e.target.value)}
          placeholder="Km inicial"
          required
          min={0}
          className="h-[30px] w-[90px] rounded-md border border-border bg-surface px-2 text-xs text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft"
        />
        <button type="submit" className={`${btnBase} ${btnGreen}`} disabled={loading}>
          {loading ? "..." : "Confirmar início"}
        </button>
        <button type="button" className={btnBase} onClick={() => setShowStart(false)}>✕</button>
        {error && <p className={errorCls}>{error}</p>}
      </form>
    );
  }

  if (trip.status === "in_progress") {
    if (showComplete) {
      return (
        <form onSubmit={handleComplete} className="flex items-center gap-1.5">
          <input
            type="number"
            value={kmEnd}
            onChange={(e) => setKmEnd(e.target.value)}
            placeholder="Km final"
            required
            min={0}
            className="w-[90px] h-[30px] px-2 border border-border rounded-md bg-surface text-ink text-xs focus:outline-none focus:border-focus focus:ring-2 focus:ring-focus-soft"
          />
          <button type="submit" className={`${btnBase} ${btnGreen}`} disabled={loading}>
            {loading ? "..." : "Confirmar"}
          </button>
          <button type="button" className={btnBase} onClick={() => setShowComplete(false)}>✕</button>
          {error && <p className={errorCls}>{error}</p>}
        </form>
      );
    }
    return (
      <button className={`${btnBase} ${btnCyan}`} onClick={() => setShowComplete(true)} title="Concluir viagem">
        <CheckCircle size={14} />
        Concluir
      </button>
    );
  }

  return null;
}
