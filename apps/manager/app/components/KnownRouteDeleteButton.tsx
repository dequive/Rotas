"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function KnownRouteDeleteButton({ routeId, routeLabel }: { routeId: string; routeLabel: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleDelete() {
    if (!confirm(`Eliminar rota "${routeLabel}"?`)) return;
    setLoading(true);
    await fetch("/api/known-routes", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: routeId }),
    });
    setLoading(false);
    router.refresh();
  }

  return (
    <button className="icon-btn danger" onClick={handleDelete} disabled={loading} title="Eliminar rota">
      <Trash2 size={15} />
    </button>
  );
}
