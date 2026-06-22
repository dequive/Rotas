import { apiFetch } from "@/app/lib/api";
import { requireSession } from "@/app/lib/auth";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { DespachoClient } from "./DespachoClient";

type Trip = {
  id: string;
  origin: string;
  destination: string;
  status: string;
  actual_departure: string | null;
  actual_arrival: string | null;
  driver_id: string | null;
  vehicle_id: string | null;
};

type Settlement = {
  id: string;
  trip_id: string;
  advance_amount_mzn: string;
  total_costs_mzn: string;
  balance_mzn: string;
  status: "pending" | "approved" | "rejected";
  rejection_reason: string | null;
  pdf_file_id: string | null;
};

type Advance = {
  id: string;
  amount_mzn: string;
  status: string;
  notes: string | null;
};

async function loadTrips(status: string): Promise<Trip[]> {
  try {
    return await apiFetch<Trip[]>(`/api/v1/trips?status=${status}&limit=100`, {
      revalidate: 0,
    });
  } catch {
    return [];
  }
}

async function loadSettlement(tripId: string): Promise<Settlement | null> {
  try {
    return await apiFetch<Settlement>(`/api/v1/trips/${tripId}/settlement`, {
      revalidate: 0,
    });
  } catch {
    return null;
  }
}

async function loadAdvance(tripId: string): Promise<Advance | null> {
  try {
    const list = await apiFetch<Advance[]>(`/api/v1/trips/${tripId}/advance`, {
      revalidate: 0,
    });
    return list.find((a) => a.status !== "voided") ?? null;
  } catch {
    return null;
  }
}

export default async function DespachoPage() {
  await requireSession();

  const [planned, inProgress, completed] = await Promise.all([
    loadTrips("planned"),
    loadTrips("in_progress"),
    loadTrips("completed"),
  ]);

  const activeTrips = [...planned, ...inProgress];

  // Load settlement + advance for each completed trip in parallel (max 50)
  const sliced = completed.slice(0, 50);
  const enriched = await Promise.all(
    sliced.map(async (trip) => {
      const [settlement, advance] = await Promise.all([
        loadSettlement(trip.id),
        loadAdvance(trip.id),
      ]);
      return { trip, settlement, advance };
    })
  );

  return (
    <SidebarLayout active="despacho">
      <div className="w-full">
        <div className="mb-6">
          <PageHeader
            title="Despacho de Motoristas"
            description="Adiantamentos em numerário e liquidação financeira de viagens concluídas."
          />
        </div>

        <DespachoClient activeTrips={activeTrips} completedRows={enriched} />
      </div>
    </SidebarLayout>
  );
}
