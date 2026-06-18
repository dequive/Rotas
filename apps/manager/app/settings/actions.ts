"use server";

import { apiFetch } from "@/app/lib/api";

export async function updateUserProfile(
  userId: string,
  data: { full_name: string; email: string; phone: string | null }
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await apiFetch(`/api/v1/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Erro desconhecido ao guardar alterações." };
  }
}
