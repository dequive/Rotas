"use server";

import { apiFetch } from "@/app/lib/api";
import { revalidatePath } from "next/cache";

export async function updateUserProfile(
  userId: string,
  data: { full_name: string; email: string; phone: string | null }
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await apiFetch(`/api/v1/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
    revalidatePath("/settings");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Erro desconhecido ao guardar alterações." };
  }
}

export async function inviteUser(data: {
  email: string;
  full_name: string;
  password: string;
  role: string;
  phone?: string;
}): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await apiFetch("/api/v1/users", {
      method: "POST",
      body: JSON.stringify(data),
    });
    revalidatePath("/settings");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Erro ao criar utilizador." };
  }
}

export async function changeUserRole(
  userId: string,
  role: string
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await apiFetch(`/api/v1/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
    revalidatePath("/settings");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Erro ao alterar role." };
  }
}

export async function updateTenantSettings(data: {
  timezone?: string;
  currency?: string;
  whatsapp_number?: string;
}): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await apiFetch("/api/v1/tenants/me", {
      method: "PATCH",
      body: JSON.stringify(data),
    });
    revalidatePath("/settings");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Erro ao guardar configurações." };
  }
}
