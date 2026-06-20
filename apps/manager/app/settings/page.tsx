import { requireSession } from "@/app/lib/auth";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { SettingsClient } from "./SettingsClient";
import { apiFetch } from "@/app/lib/api";
import type { TenantLimits } from "@/app/components/LimitWarningBanner";

interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: string;
}

interface TenantData {
  id: string;
  name: string;
  slug: string;
  plan: string;
  timezone: string;
  currency: string;
}

interface DriverBasic {
  id: string;
  full_name: string;
  phone: string;
  status: string;
}

async function getTenantLimits(): Promise<TenantLimits | null> {
  try {
    return await apiFetch<TenantLimits>("/api/v1/tenants/me/limits", { revalidate: 30 });
  } catch {
    return null;
  }
}

async function getUsers(): Promise<UserResponse[]> {
  try {
    return await apiFetch<UserResponse[]>("/api/v1/users?limit=50", { revalidate: 15 });
  } catch {
    return [];
  }
}

async function getTenant(): Promise<TenantData | null> {
  try {
    return await apiFetch<TenantData>("/api/v1/tenants/me", { revalidate: 30 });
  } catch {
    return null;
  }
}

async function getDrivers(): Promise<DriverBasic[]> {
  try {
    return await apiFetch<DriverBasic[]>("/api/v1/drivers?limit=100", { revalidate: 30 });
  } catch {
    return [];
  }
}

export default async function SettingsPage() {
  const session = await requireSession();

  const [limits, users, tenant, drivers] = await Promise.all([
    getTenantLimits(),
    getUsers(),
    getTenant(),
    getDrivers(),
  ]);

  // Find current logged in user details
  const currentUser = users.find((u) => u.id === session.userId);

  return (
    <SidebarLayout active="settings">
      <div className="w-full max-w-4xl mx-auto space-y-6">
        <PageHeader
          title="Definições da Conta"
          description="Gira as suas preferências, acessos e os limites do plano subscrito com sincronização no banco de dados."
        />

        <SettingsClient
          userId={session.userId}
          userRole={currentUser?.role ?? session.role}
          initialName={currentUser?.full_name ?? session.fullName}
          initialEmail={currentUser?.email ?? ""}
          initialPhone={currentUser?.phone ?? ""}
          limits={limits}
          users={users}
          tenant={tenant}
          drivers={drivers}
        />
      </div>
    </SidebarLayout>
  );
}
