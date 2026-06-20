"use server";

import { apiFetch } from "@/app/lib/api";
import type { Alert } from "@/app/lib/alerts-api";

export async function resolveAlert(alertId: string): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await apiFetch<Alert>(`/api/v1/alerts/${alertId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: "resolved" }),
    });
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Erro desconhecido." };
  }
}

export async function acknowledgeAlert(alertId: string): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await apiFetch<Alert>(`/api/v1/alerts/${alertId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: "read" }),
    });
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Erro desconhecido." };
  }
}
