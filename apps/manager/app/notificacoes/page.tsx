import { requireSession } from "@/app/lib/auth";
import { apiFetch } from "@/app/lib/api";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { NotificacoesClient } from "./NotificacoesClient";
import type { Notification } from "@/app/lib/notifications-api";

async function getNotifications(): Promise<{ data: Notification[]; error: string | null }> {
  try {
    const data = await apiFetch<Notification[]>("/api/v1/notifications?limit=100", {
      revalidate: 10,
    });
    return { data, error: null };
  } catch (err) {
    return {
      data: [],
      error: err instanceof Error ? err.message : "Erro ao carregar notificações.",
    };
  }
}

export default async function NotificacoesPage() {
  await requireSession();

  const { data: notifications, error } = await getNotifications();

  return (
    <SidebarLayout active="notificacoes">
      <div className="w-full max-w-5xl mx-auto space-y-6">
        <PageHeader
          title="Notificações"
          description="Fila de saída de e-mails e mensagens do sistema — estado de entrega, tentativas e erros."
        />

        <NotificacoesClient notifications={notifications} error={error} />
      </div>
    </SidebarLayout>
  );
}
