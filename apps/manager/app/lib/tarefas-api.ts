import { apiFetch, extractApiError } from "./api";
import { requireSession } from "./auth";

export type TaskStatus = "pending" | "in_progress" | "review" | "completed" | "cancelled";

export interface UnifiedTask {
  id: string;
  source: "workshop" | "governance";
  title: string;
  category: string;
  status: TaskStatus;
  createdAt: string;
  slaDueAt?: string;
  assigneeId?: string;
  tenantId: string;
}

export async function getUnifiedTasks(): Promise<UnifiedTask[]> {
  try {
    // 1. Fetch Maintenance Requests (Workshop)
    // using apiFetch which points to ROTAS_API_BASE_URL
    const maintenanceRequests = await apiFetch<any[]>("/api/v1/workshop/maintenance-requests").catch(() => []);

    // 2. Fetch Governance Cases
    // using direct fetch since apiFetch uses ROTAS_API_BASE_URL
    const GOVERNANCE_API = process.env.GOVERNANCE_API_URL || "http://localhost:8001";
    const session = await requireSession();
    
    const casesRes = await fetch(`${GOVERNANCE_API}/api/v1/cases`, {
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${session.accessToken}`,
        "X-Tenant-Id": session.tenantId,
      }
    }).catch(() => null);

    const cases = casesRes && casesRes.ok ? await casesRes.json() : [];

    // 3. Normalize
    const unified: UnifiedTask[] = [];

    // Map Workshop tasks
    if (Array.isArray(maintenanceRequests)) {
      maintenanceRequests.forEach((mr: any) => {
        let normalizedStatus: TaskStatus = "pending";
        if (mr.status === "approved" || mr.status === "in_progress") normalizedStatus = "in_progress";
        if (mr.status === "quality_check") normalizedStatus = "review";
        if (mr.status === "closed") normalizedStatus = "completed";

        unified.push({
          id: mr.id,
          source: "workshop",
          title: mr.description || "Pedido de Manutenção",
          category: "Mecânica/Frota",
          status: normalizedStatus,
          createdAt: mr.created_at,
          tenantId: mr.tenant_id,
        });
      });
    }

    // Map Governance Cases
    if (Array.isArray(cases)) {
      cases.forEach((c: any) => {
        let normalizedStatus: TaskStatus = "pending";
        if (c.status === "in_progress") normalizedStatus = "in_progress";
        if (c.status === "resolved") normalizedStatus = "completed";
        if (c.status === "cancelled") normalizedStatus = "cancelled";

        unified.push({
          id: c.id,
          source: "governance",
          title: c.title || "Caso Interno",
          category: c.case_type_id || "Geral", // Should map to actual taxonomy
          status: normalizedStatus,
          createdAt: c.created_at,
          slaDueAt: c.sla_due_at,
          assigneeId: c.assignee_id,
          tenantId: c.tenant_id,
        });
      });
    }

    // Sort by creation date descending
    unified.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

    return unified;
  } catch (error) {
    console.error("Failed to fetch unified tasks", error);
    return [];
  }
}
