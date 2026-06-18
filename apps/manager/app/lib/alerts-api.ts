import { apiFetch } from "./api";

export interface Alert {
  id: string;
  request_reference: string;
  alert_type: string;
  priority: "low" | "medium" | "high" | "critical";
  entity_type: string | null;
  entity_id: string | null;
  title: string;
  message: string | null;
  channel: string;
  status: "pending" | "read" | "dismissed" | "resolved";
  sent_at: string | null;
  created_at: string;
}

export async function loadAlerts(params?: {
  status?: string;
  priority?: string;
  alert_type?: string;
}): Promise<Alert[]> {
  let query = "";
  if (params) {
    const parts = [];
    if (params.status) parts.push(`status=${params.status}`);
    if (params.priority) parts.push(`priority=${params.priority}`);
    if (params.alert_type) parts.push(`alert_type=${params.alert_type}`);
    if (parts.length > 0) {
      query = "?" + parts.join("&");
    }
  }
  return await apiFetch<Alert[]>(`/api/v1/alerts${query}`, { revalidate: 5 });
}

export async function updateAlertStatus(alertId: string, status: string): Promise<Alert> {
  return await apiFetch<Alert>(`/api/v1/alerts/${alertId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
