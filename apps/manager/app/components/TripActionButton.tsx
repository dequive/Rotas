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
  const [kmEnd, setKmEnd] = useState("");

  async function handleStart() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/trips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ _action: "start", id: trip.id }),
      });
      if (!res.ok) {
        const body = (await res.json()) as { detail?: string; error?: { message?: string; code?: string } };
        setError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao iniciar viagem.");
        return;
      }
      router.refresh();
    } finally {
      setLoading(false);
    }
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

  if (trip.status === "planned" || trip.status === "dispatched") {
    return (
      <div>
        <button className={`${btnBase} ${btnGreen}`} onClick={handleStart} disabled={loading} title="Iniciar viagem">
          <Play size={14} />
          {loading ? "..." : "Iniciar"}
        </button>
        {error && <p className={errorCls}>{error}</p>}
      </div>
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
            className="w-[90px] h-[30px] px-2 border border-border rounded-md bg-surface text-ink text-xs focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
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
