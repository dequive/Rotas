"use server";

import { randomUUID } from "node:crypto";
import { revalidatePath } from "next/cache";

import { apiFetch } from "../../../lib/api";

export type WorkOrderActionResult = { ok: true } | { ok: false; error: string };

async function mutate(path: string, body?: unknown): Promise<WorkOrderActionResult> {
  try {
    await apiFetch(path, {
      method: "POST",
      headers: { "Idempotency-Key": randomUUID() },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    revalidatePath("/oficina/ordens-servico");
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Operação não concluída." };
  }
}

export async function transitionWorkOrder(
  workOrderId: string,
  transition: "approve" | "start" | "quality-check" | "close",
  notes: string,
  actualCost?: number,
): Promise<WorkOrderActionResult> {
  const body = transition === "close" ? { notes, actual_cost: actualCost ?? 0 } : { notes };
  return mutate(`/api/v1/workshop/work-orders/${workOrderId}/${transition}`, body);
}

export async function addLaborSession(
  taskId: string,
  userId: string,
  minutesWorked: number,
): Promise<WorkOrderActionResult> {
  return mutate(`/api/v1/workshop/tasks/${taskId}/labor`, {
    user_id: userId,
    minutes_worked: minutesWorked,
  });
}

export async function issuePart(
  workOrderId: string,
  inventoryId: string,
  quantity: number,
  notes?: string,
): Promise<WorkOrderActionResult> {
  return mutate(`/api/v1/workshop/work-orders/${workOrderId}/parts/issue`, {
    inventory_id: inventoryId,
    quantity,
    notes: notes || null,
  });
}

export async function returnPart(
  workOrderId: string,
  inventoryId: string,
  quantity: number,
  reason: string,
): Promise<WorkOrderActionResult> {
  return mutate(`/api/v1/workshop/work-orders/${workOrderId}/parts/return`, {
    inventory_id: inventoryId,
    quantity,
    reason,
  });
}

export async function retryBilling(workOrderId: string): Promise<WorkOrderActionResult> {
  return mutate(`/api/v1/workshop/work-orders/${workOrderId}/billing/retry`);
}

export async function completeWorkOrderTask(
  workOrderId: string,
  taskId: string,
  actualMinutes: number,
  notes: string,
): Promise<WorkOrderActionResult> {
  return mutate(
    `/api/v1/workshop/work-orders/${workOrderId}/tasks/${taskId}/complete`,
    {
      actual_minutes: actualMinutes,
      notes: notes.trim() || null,
    },
  );
}

export async function confirmWorkshopInvoice(
  documentId: string,
): Promise<WorkOrderActionResult> {
  return mutate(`/api/v1/workshop/invoices/${documentId}/confirm`);
}

export async function releaseVehicle(
  receptionId: string,
  payload: {
    odometer_at_release: number;
    condition_at_release: string;
    picked_up_by_name: string;
    picked_up_by_phone: string | null;
    override_unauthorized_pickup: boolean;
    override_reason: string | null;
    client_signature_file_id: string;
    release_type: "after_service";
    notes: string | null;
  },
): Promise<WorkOrderActionResult> {
  return mutate(`/api/v1/workshop/receptions/${receptionId}/release`, payload);
}
