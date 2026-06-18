"use server";

import { apiFetch } from "@/app/lib/api";

export async function updateUserProfile(
  userId: string,
  data: { full_name: string; email: string; phone: string | null }
): Promise<void> {
  await apiFetch(`/api/v1/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
