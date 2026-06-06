"use client";

import { CheckCircle, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Trip } from "../lib/trips-api";

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
        const body = (await res.json()) as { detail?: string };
        setError(body.detail ?? "Erro ao iniciar viagem.");
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
        const body = (await res.json()) as { detail?: string };
        setError(body.detail ?? "Erro ao concluir viagem.");
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
        <button className="action-btn green" onClick={handleStart} disabled={loading} title="Iniciar viagem">
          <Play size={14} />
          {loading ? "..." : "Iniciar"}
        </button>
        {error && <p className="form-error">{error}</p>}
      </div>
    );
  }

  if (trip.status === "in_progress") {
    if (showComplete) {
      return (
        <form onSubmit={handleComplete} className="inline-form">
          <input
            type="number"
            value={kmEnd}
            onChange={(e) => setKmEnd(e.target.value)}
            placeholder="Km final"
            required
            min={0}
            className="km-input"
          />
          <button type="submit" className="action-btn green" disabled={loading}>
            {loading ? "..." : "Confirmar"}
          </button>
          <button type="button" className="action-btn" onClick={() => setShowComplete(false)}>✕</button>
          {error && <p className="form-error">{error}</p>}
        </form>
      );
    }
    return (
      <button className="action-btn cyan" onClick={() => setShowComplete(true)} title="Concluir viagem">
        <CheckCircle size={14} />
        Concluir
      </button>
    );
  }

  return null;
}
