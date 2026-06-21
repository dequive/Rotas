import { apiFetch } from "./api";

export interface Notification {
  id: string;
  tenant_id: string;
  request_reference: string;
  channel: string;
  recipient: string;
  subject: string;
  body_text: string;
  body_html: string | null;
  template: string | null;
  payload: Record<string, unknown> | null;
  status: "queued" | "sent" | "failed" | "cancelled";
  attempts: number;
  last_error: string | null;
  scheduled_at: string | null;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export async function loadNotifications(params?: {
  status?: string;
  channel?: string;
  limit?: number;
  offset?: number;
}): Promise<Notification[]> {
  const parts: string[] = [];
  if (params?.status) parts.push(`status=${encodeURIComponent(params.status)}`);
  if (params?.channel) parts.push(`channel=${encodeURIComponent(params.channel)}`);
  if (params?.limit != null) parts.push(`limit=${params.limit}`);
  if (params?.offset != null) parts.push(`offset=${params.offset}`);
  const query = parts.length > 0 ? `?${parts.join("&")}` : "";
  return await apiFetch<Notification[]>(`/api/v1/notifications${query}`, { revalidate: 10 });
}
