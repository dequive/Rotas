"use server";

import { revalidatePath } from "next/cache";
import { apiFetch } from "@/app/lib/api";

export async function issueBillingDocument(
  documentId: string,
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await apiFetch(`/api/v1/billing/documents/${documentId}/issue`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    revalidatePath("/cobranca");
    return { ok: true };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Erro ao emitir documento.",
    };
  }
}
