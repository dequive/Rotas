"use client";

import { useState } from "react";
import { Mail, Send, XCircle, Clock, AlertCircle, CheckCircle2 } from "lucide-react";
import { SectionHeader } from "@/app/components/ui/SectionHeader";
import { EmptyState } from "@/app/components/ui/EmptyState";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import type { Notification } from "@/app/lib/notifications-api";

type StatusFilter = "queued" | "sent" | "failed" | "cancelled" | "all";

interface Props {
  notifications: Notification[];
  error: string | null;
}

const STATUS_LABELS: Record<StatusFilter, string> = {
  all: "Todas",
  queued: "Na fila",
  sent: "Enviadas",
  failed: "Falhadas",
  cancelled: "Canceladas",
};

const STATUS_BADGE_MAP: Record<Notification["status"], string> = {
  queued: "alerta",
  sent: "ativo",
  failed: "expired",
  cancelled: "inativo",
};

const CHANNEL_ICONS: Record<string, React.ElementType> = {
  email: Mail,
  whatsapp: Send,
  sms: Send,
};

function formatTs(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString("pt-MZ");
}

export function NotificacoesClient({ notifications, error }: Props) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const filtered =
    statusFilter === "all"
      ? notifications
      : notifications.filter((n) => n.status === statusFilter);

  const counts: Record<StatusFilter, number> = {
    all: notifications.length,
    queued: notifications.filter((n) => n.status === "queued").length,
    sent: notifications.filter((n) => n.status === "sent").length,
    failed: notifications.filter((n) => n.status === "failed").length,
    cancelled: notifications.filter((n) => n.status === "cancelled").length,
  };

  return (
    <div className="space-y-6">
      {/* Status filter pills */}
      <div className="flex flex-wrap gap-1">
        {(["all", "queued", "sent", "failed", "cancelled"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 text-[12px] font-semibold rounded-md border transition-colors duration-75 ${
              statusFilter === s
                ? "bg-amber-light border-amber text-amber-dark"
                : "bg-surface border-border text-muted hover:text-ink"
            }`}
          >
            {STATUS_LABELS[s]} ({counts[s]})
          </button>
        ))}
      </div>

      <SectionHeader title="Notificações" count={filtered.length} />

      {error && (
        <div className="p-3 bg-error-bg border border-error/30 rounded-md text-xs font-semibold text-error">
          {error}
        </div>
      )}

      {!error && filtered.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <EmptyState
            icon={CheckCircle2}
            title="Sem notificações"
            description={
              statusFilter === "all"
                ? "Nenhuma notificação registada ainda."
                : `Sem notificações com estado "${STATUS_LABELS[statusFilter]}".`
            }
          />
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((n) => {
            const ChannelIcon = CHANNEL_ICONS[n.channel] ?? Mail;
            return (
              <div
                key={n.id}
                className="flex flex-col md:flex-row md:items-start justify-between p-4 bg-surface border border-border rounded-lg shadow-sm gap-4"
              >
                {/* Left: meta */}
                <div className="space-y-1.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <StatusBadge
                      status={STATUS_BADGE_MAP[n.status] as Parameters<typeof StatusBadge>[0]["status"]}
                      label={STATUS_LABELS[n.status]}
                    />
                    <span className="inline-flex items-center gap-1 text-[11px] font-mono text-muted uppercase tracking-wide">
                      <ChannelIcon size={12} />
                      {n.channel}
                    </span>
                    {n.attempts > 0 && (
                      <span className="text-[11px] font-mono text-muted">
                        {n.attempts} tentativa{n.attempts !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>

                  <h4 className="text-[13px] font-bold text-ink truncate">{n.subject}</h4>

                  <p className="text-[12px] font-mono text-ink-2 truncate">{n.recipient}</p>

                  {n.last_error && (
                    <div className="flex items-start gap-1.5 mt-1">
                      <AlertCircle size={12} className="text-error mt-0.5 shrink-0" />
                      <p className="text-[11px] text-error font-mono break-all">{n.last_error}</p>
                    </div>
                  )}

                  <p className="text-[11px] font-mono text-muted truncate">
                    ref: {n.request_reference}
                  </p>
                </div>

                {/* Right: timestamps */}
                <div className="flex flex-col gap-1 shrink-0 text-right">
                  <span className="flex items-center gap-1 text-[11px] text-muted justify-end">
                    <Clock size={11} />
                    Criada: {formatTs(n.created_at)}
                  </span>
                  {n.scheduled_at && (
                    <span className="text-[11px] text-muted font-mono">
                      Agendada: {formatTs(n.scheduled_at)}
                    </span>
                  )}
                  {n.sent_at && (
                    <span className="text-[11px] text-ink-2 font-mono">
                      Enviada: {formatTs(n.sent_at)}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
