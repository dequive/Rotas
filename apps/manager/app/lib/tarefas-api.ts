import { apiFetch } from "./api";
import { requireSession } from "./auth";
import { governanceRequest } from "./governance-bff";

export type TaskStatus = "pending" | "in_progress" | "review" | "completed" | "cancelled";
export type TaskSource = "workshop" | "governance";

export interface UnifiedTask {
  id: string;
  source: TaskSource;
  title: string;
  category: string;
  status: TaskStatus;
  createdAt: string;
  slaDueAt?: string;
  assigneeId?: string;
  tenantId: string;
}

export interface UnifiedTasksResult {
  tasks: UnifiedTask[];
  unavailableSources: TaskSource[];
}

interface WorkshopTask {
  id: string;
  tenant_id: string;
  description: string;
  status: string;
  created_at: string;
}

interface GovernanceCase {
  id: string;
  case_type_code: string;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
  sla_due_at?: string | null;
  assignee_id?: string | null;
}

function normalizeStatus(status: string): TaskStatus {
  if (["cancelled", "rejected"].includes(status)) return "cancelled";
  if (["resolved", "closed", "completed", "converted"].includes(status)) return "completed";
  if (["quality_check", "review"].includes(status)) return "review";
  if (["approved", "in_progress", "in_analysis", "triaged"].includes(status)) return "in_progress";
  return "pending";
}

export async function getUnifiedTasks(): Promise<UnifiedTasksResult> {
  const session = await requireSession();
  const unavailableSources: TaskSource[] = [];
  const tasks: UnifiedTask[] = [];

  const [workshopResult, governanceResult] = await Promise.allSettled([
    apiFetch<WorkshopTask[]>("/api/v1/workshop/maintenance-requests"),
    governanceRequest("/api/v1/cases/"),
  ]);

  if (workshopResult.status === "fulfilled") {
    for (const item of workshopResult.value) {
      tasks.push({
        id: item.id,
        source: "workshop",
        title: item.description || "Pedido de manutenção",
        category: "Mecânica/Frota",
        status: normalizeStatus(item.status),
        createdAt: item.created_at,
        tenantId: item.tenant_id,
      });
    }
  } else {
    unavailableSources.push("workshop");
  }

  if (governanceResult.status === "fulfilled" && governanceResult.value.ok) {
    const body = (await governanceResult.value.json().catch(() => null)) as
      | { items?: GovernanceCase[] }
      | null;
    if (Array.isArray(body?.items)) {
      for (const item of body.items) {
        tasks.push({
          id: item.id,
          source: "governance",
          title:
            typeof item.payload?.title === "string"
              ? item.payload.title
              : item.case_type_code,
          category: item.case_type_code,
          status: normalizeStatus(item.status),
          createdAt: item.created_at,
          ...(item.sla_due_at ? { slaDueAt: item.sla_due_at } : {}),
          ...(item.assignee_id ? { assigneeId: item.assignee_id } : {}),
          tenantId: session.tenantId,
        });
      }
    } else {
      unavailableSources.push("governance");
    }
  } else {
    unavailableSources.push("governance");
  }

  tasks.sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  return { tasks, unavailableSources };
}
