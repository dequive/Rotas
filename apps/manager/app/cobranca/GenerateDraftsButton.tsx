"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ReceiptText, Loader2 } from "lucide-react";
import { BillingTrip } from "@/app/lib/billing-api";
import { bffRequest } from "@/app/lib/bff";

export function GenerateDraftsButton({ trips }: { trips: BillingTrip[] }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const billableTrips = trips.filter(t => t.status === "billable");

  async function handleGenerate() {
    setLoading(true);
    setError(null);

    // Group trips by client
    const tripsByClient = billableTrips.reduce((acc, trip) => {
      const client = trip.client ?? "Cliente Desconhecido";
      if (!acc[client]) acc[client] = [];
      acc[client].push(trip);
      return acc;
    }, {} as Record<string, BillingTrip[]>);

    try {
      const headers = {
        "Content-Type": "application/json"
      };

      // Create a draft document for each client
      for (const [clientName, clientTrips] of Object.entries(tripsByClient)) {
        const payload = {
          client_name: clientName,
          billing_period_start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
          billing_period_end: new Date().toISOString(),
          currency: "MZN",
          trip_ids: clientTrips.map(t => t.id),
          client_nuit: "000000000" // Default NUIT since we bypass validation for drafts usually
        };

        const res = await bffRequest("/api/v1/billing/documents", {
          method: "POST",
          headers,
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          throw new Error(`Erro ao gerar fatura para ${clientName}`);
        }
      }

      router.refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (billableTrips.length === 0) {
    return (
      <button
        disabled
        className="inline-flex items-center gap-1.5 h-9 px-4 text-[13px] font-semibold bg-indigo-600/50 text-white border-0 rounded-md cursor-not-allowed"
        title="Selecione viagens prontas a cobrar para gerar um documento de cobrança"
      >
        <ReceiptText size={15} />
        Gerar Documento
      </button>
    );
  }

  return (
    <div className="flex flex-col items-end">
      <button
        onClick={handleGenerate}
        disabled={loading}
        className="inline-flex items-center gap-1.5 h-9 px-4 text-[13px] font-semibold bg-indigo-600 hover:bg-indigo-700 text-white border-0 rounded-md shadow-sm transition-colors"
        title={`Gerar Faturas para ${billableTrips.length} viagens`}
      >
        {loading ? <Loader2 size={15} className="animate-spin" /> : <ReceiptText size={15} />}
        {loading ? "A Gerar..." : `Gerar Faturas (${billableTrips.length})`}
      </button>
      {error && <span className="text-xs text-rose-500 mt-1">{error}</span>}
    </div>
  );
}
