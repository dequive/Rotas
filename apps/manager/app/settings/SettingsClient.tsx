"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { User, ShieldCheck, Settings, Zap } from "lucide-react";
import { SectionHeader } from "@/app/components/ui/SectionHeader";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import type { TenantLimits } from "@/app/components/LimitWarningBanner";
import { updateUserProfile, inviteUser, changeUserRole, updateTenantSettings } from "./actions";

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

interface Props {
  userId: string;
  userRole: string;
  initialName: string;
  initialEmail: string;
  initialPhone: string;
  limits: TenantLimits | null;
  users: UserResponse[];
  tenant: TenantData | null;
  drivers: DriverBasic[];
}

const DRIVER_STATUS_LABEL: Record<string, string> = {
  active: "Activo",
  inactive: "Inactivo",
  suspended: "Suspenso",
};

export function SettingsClient({
  userId,
  userRole,
  initialName,
  initialEmail,
  initialPhone,
  limits,
  users,
  tenant,
  drivers,
}: Props) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"perfil" | "acessos" | "preferencias">("perfil");

  // ── Perfil tab state ──────────────────────────────────────────────────────
  const [fullName, setFullName] = useState(initialName);
  const [email, setEmail] = useState(initialEmail);
  const [phone, setPhone] = useState(initialPhone || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // ── Acessos tab state ─────────────────────────────────────────────────────
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);
  const [roleChangingId, setRoleChangingId] = useState<string | null>(null);

  // ── Preferências tab state ────────────────────────────────────────────────
  const [timezone, setTimezone] = useState(tenant?.timezone ?? "Africa/Maputo");
  const [currency, setCurrency] = useState(tenant?.currency ?? "MZN");
  const [whatsapp, setWhatsapp] = useState("");
  const [tenantLoading, setTenantLoading] = useState(false);
  const [tenantError, setTenantError] = useState<string | null>(null);
  const [tenantSuccess, setTenantSuccess] = useState<string | null>(null);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    const result = await updateUserProfile(userId, {
      full_name: fullName,
      email,
      phone: phone || null,
    });

    if (result.ok) {
      setSuccess("Perfil atualizado com sucesso!");
      router.refresh();
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  const handleInviteUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteLoading(true);
    setInviteError(null);
    setInviteSuccess(null);
    const result = await inviteUser({ email: inviteEmail, full_name: inviteName, role: inviteRole });
    if (result.ok) {
      setInviteSuccess("Utilizador convidado com sucesso!");
      setInviteEmail("");
      setInviteName("");
      setInviteRole("viewer");
      router.refresh();
    } else {
      setInviteError(result.error);
    }
    setInviteLoading(false);
  };

  const handleSaveTenantSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setTenantLoading(true);
    setTenantError(null);
    setTenantSuccess(null);
    const result = await updateTenantSettings({
      timezone,
      currency,
      whatsapp_number: whatsapp || undefined,
    });
    if (result.ok) {
      setTenantSuccess("Configurações guardadas!");
      router.refresh();
    } else {
      setTenantError(result.error);
    }
    setTenantLoading(false);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {/* Settings Navigation Menu */}
      <div className="flex flex-col gap-2">
        <button
          onClick={() => setActiveTab("perfil")}
          className={`flex items-center gap-3 px-4 py-3 border rounded-lg text-left text-[14px] font-semibold transition-colors duration-75 ${
            activeTab === "perfil"
              ? "bg-surface border-amber text-ink shadow-sm"
              : "bg-transparent hover:bg-surface-2 border-transparent text-muted"
          }`}
        >
          <User size={18} className={activeTab === "perfil" ? "text-amber" : ""} />
          Perfil
        </button>
        <button
          onClick={() => setActiveTab("acessos")}
          className={`flex items-center gap-3 px-4 py-3 border rounded-lg text-left text-[14px] font-semibold transition-colors duration-75 ${
            activeTab === "acessos"
              ? "bg-surface border-amber text-ink shadow-sm"
              : "bg-transparent hover:bg-surface-2 border-transparent text-muted"
          }`}
        >
          <ShieldCheck size={18} className={activeTab === "acessos" ? "text-amber" : ""} />
          Gestão de Acessos
        </button>
        <button
          onClick={() => setActiveTab("preferencias")}
          className={`flex items-center gap-3 px-4 py-3 border rounded-lg text-left text-[14px] font-semibold transition-colors duration-75 ${
            activeTab === "preferencias"
              ? "bg-surface border-amber text-ink shadow-sm"
              : "bg-transparent hover:bg-surface-2 border-transparent text-muted"
          }`}
        >
          <Settings size={18} className={activeTab === "preferencias" ? "text-amber" : ""} />
          Preferências
        </button>
      </div>

      {/* Content Area */}
      <div className="md:col-span-2 flex flex-col gap-6">
        {/* ── PERFIL TAB ──────────────────────────────────────────────────── */}
        {activeTab === "perfil" && (
          <>
            <section className="bg-surface border border-border rounded-lg p-6">
              <SectionHeader title="Dados do Perfil" />

              <form onSubmit={handleSaveProfile} className="space-y-4 mt-4">
                {error && (
                  <div className="p-3 bg-error-bg text-error rounded-md text-xs font-semibold">
                    {error}
                  </div>
                )}
                {success && (
                  <div className="p-3 bg-success-bg text-success rounded-md text-xs font-semibold">
                    {success}
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[12px] font-semibold text-muted uppercase tracking-wide">Nome Completo</label>
                    <input
                      type="text"
                      className="h-10 px-3 bg-surface border border-border rounded-md text-[14px] text-ink focus:outline-none focus:border-amber"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      required
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[12px] font-semibold text-muted uppercase tracking-wide">Email</label>
                    <input
                      type="email"
                      className="h-10 px-3 bg-surface border border-border rounded-md text-[14px] text-ink focus:outline-none focus:border-amber"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[12px] font-semibold text-muted uppercase tracking-wide">Telefone</label>
                    <input
                      type="text"
                      className="h-10 px-3 bg-surface border border-border rounded-md text-[14px] text-ink focus:outline-none focus:border-amber"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="Ex: +258 84..."
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[12px] font-semibold text-muted uppercase tracking-wide">Cargo / Nível de Acesso</label>
                    <input
                      type="text"
                      className="h-10 px-3 bg-surface-2 border border-border rounded-md text-[14px] text-muted cursor-not-allowed uppercase"
                      value={userRole}
                      disabled
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    type="submit"
                    disabled={loading}
                    className="inline-flex items-center justify-center h-10 px-6 text-[13px] font-semibold bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity duration-75 disabled:opacity-50"
                  >
                    {loading ? "A guardar..." : "Guardar Alterações"}
                  </button>
                </div>
              </form>
            </section>

            <section className="bg-surface border border-border rounded-lg p-6">
              <SectionHeader title="Limites do Plano" />
              <div className="mt-4">
                {limits ? (
                  <div className="flex flex-col gap-5">
                    <div className="flex items-center gap-3 p-4 bg-amber-light/20 border border-amber/30 rounded-lg">
                      <div className="h-10 w-10 bg-amber-light flex items-center justify-center rounded-full text-amber-dark">
                        <Zap size={20} />
                      </div>
                      <div>
                        <strong className="block text-[14px] text-ink">Plano Ativo</strong>
                        <span className="text-[12px] text-muted">Controlo operacional e faturamento integrado.</span>
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between items-end mb-2">
                        <span className="text-[13px] font-semibold text-ink">Viaturas Activas</span>
                        <span className="text-[12px] text-muted font-mono">
                          {limits.vehicles.used} / {limits.vehicles.max ?? "∞"}
                        </span>
                      </div>
                      <div className="h-2 w-full bg-surface-2 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue"
                          style={{ width: `${limits.vehicles.pct ?? 0}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-[13px] text-muted">A carregar limites da subscrição...</p>
                )}
              </div>
            </section>
          </>
        )}

        {/* ── ACESSOS TAB ─────────────────────────────────────────────────── */}
        {activeTab === "acessos" && (
          <>
            {/* User list */}
            <section className="bg-surface border border-border rounded-lg overflow-hidden">
              <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                <h3 className="text-[13px] font-semibold text-ink uppercase tracking-wide">
                  Utilizadores ({users.length})
                </h3>
              </div>
              <div className="divide-y divide-border">
                {users.length === 0 ? (
                  <p className="px-4 py-6 text-[13px] text-muted text-center">Nenhum utilizador encontrado.</p>
                ) : (
                  users.map((u) => (
                    <div key={u.id} className="px-4 py-3 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[14px] font-semibold text-ink">{u.full_name}</p>
                        <p className="text-[12px] text-muted font-mono">{u.email}</p>
                      </div>
                      <select
                        value={u.role}
                        disabled={roleChangingId === u.id || u.id === userId}
                        onChange={async (e) => {
                          setRoleChangingId(u.id);
                          await changeUserRole(u.id, e.target.value);
                          router.refresh();
                          setRoleChangingId(null);
                        }}
                        className="h-8 px-2 text-[12px] border border-border rounded-md bg-surface focus:outline-none focus:border-amber disabled:opacity-50"
                      >
                        {["owner", "admin", "manager", "viewer"].map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    </div>
                  ))
                )}
              </div>
            </section>

            {/* Invite form — only owner/admin */}
            {(userRole === "owner" || userRole === "admin") && (
              <section className="bg-surface border border-border rounded-lg p-5">
                <SectionHeader title="Convidar Utilizador" />
                <form onSubmit={handleInviteUser} className="mt-4 space-y-3">
                  {inviteError && (
                    <div className="p-3 bg-error-bg text-error rounded-md text-xs font-semibold">
                      {inviteError}
                    </div>
                  )}
                  {inviteSuccess && (
                    <div className="p-3 bg-success-bg text-success rounded-md text-xs font-semibold">
                      {inviteSuccess}
                    </div>
                  )}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <input
                      type="text"
                      placeholder="Nome completo"
                      value={inviteName}
                      onChange={(e) => setInviteName(e.target.value)}
                      required
                      className="h-10 px-3 bg-surface border border-border rounded-md text-[14px] text-ink placeholder:text-placeholder focus:outline-none focus:border-amber"
                    />
                    <input
                      type="email"
                      placeholder="Email"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      required
                      className="h-10 px-3 bg-surface border border-border rounded-md text-[14px] text-ink placeholder:text-placeholder focus:outline-none focus:border-amber"
                    />
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                      className="h-10 px-3 bg-surface border border-border rounded-md text-[14px] text-ink focus:outline-none focus:border-amber"
                    >
                      <option value="viewer">Viewer</option>
                      <option value="manager">Manager</option>
                      <option value="admin">Admin</option>
                    </select>
                    <button
                      type="submit"
                      disabled={inviteLoading}
                      className="h-10 px-4 text-[13px] font-semibold bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity duration-75 disabled:opacity-50"
                    >
                      {inviteLoading ? "A convidar..." : "Convidar"}
                    </button>
                  </div>
                </form>
              </section>
            )}
          </>
        )}

        {/* ── PREFERÊNCIAS TAB ────────────────────────────────────────────── */}
        {activeTab === "preferencias" && (
          <>
            {/* Tenant settings form */}
            <section className="bg-surface border border-border rounded-lg p-5">
              <SectionHeader title="Configurações da Organização" />
              <form onSubmit={handleSaveTenantSettings} className="space-y-4 mt-4">
                {tenantError && (
                  <div className="p-3 bg-error-bg text-error rounded-md text-xs font-semibold">
                    {tenantError}
                  </div>
                )}
                {tenantSuccess && (
                  <div className="p-3 bg-success-bg text-success rounded-md text-xs font-semibold">
                    {tenantSuccess}
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[12px] font-semibold text-muted uppercase tracking-wide">Fuso Horário</label>
                    <select
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                      className="h-10 px-3 bg-surface border border-border rounded-md text-[14px] text-ink focus:outline-none focus:border-amber"
                    >
                      <option value="Africa/Maputo">Africa/Maputo (UTC+2)</option>
                      <option value="UTC">UTC</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[12px] font-semibold text-muted uppercase tracking-wide">Moeda</label>
                    <select
                      value={currency}
                      onChange={(e) => setCurrency(e.target.value)}
                      className="h-10 px-3 bg-surface border border-border rounded-md text-[14px] text-ink focus:outline-none focus:border-amber"
                    >
                      <option value="MZN">MZN — Metical Moçambicano</option>
                      <option value="USD">USD — Dólar</option>
                      <option value="EUR">EUR — Euro</option>
                      <option value="ZAR">ZAR — Rand Sul-Africano</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-1.5 md:col-span-2">
                    <label className="text-[12px] font-semibold text-muted uppercase tracking-wide">WhatsApp (número da empresa)</label>
                    <input
                      type="text"
                      value={whatsapp}
                      onChange={(e) => setWhatsapp(e.target.value)}
                      placeholder="+258 84 ..."
                      className="h-10 px-3 bg-surface border border-border rounded-md text-[14px] text-ink placeholder:text-placeholder focus:outline-none focus:border-amber"
                    />
                  </div>
                </div>
                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={tenantLoading}
                    className="inline-flex items-center justify-center h-10 px-6 text-[13px] font-semibold bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity duration-75 disabled:opacity-50"
                  >
                    {tenantLoading ? "A guardar..." : "Guardar Configurações"}
                  </button>
                </div>
              </form>
            </section>

            {/* Driver roster */}
            <section className="bg-surface border border-border rounded-lg overflow-hidden">
              <div className="px-4 py-3 border-b border-border">
                <h3 className="text-[13px] font-semibold text-ink uppercase tracking-wide">
                  Motoristas Registados ({drivers.length})
                </h3>
              </div>
              <div className="divide-y divide-border max-h-64 overflow-y-auto">
                {drivers.length === 0 ? (
                  <p className="px-4 py-6 text-[13px] text-muted text-center">Nenhum motorista registado.</p>
                ) : (
                  drivers.map((d) => (
                    <div key={d.id} className="px-4 py-2.5 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[13px] font-semibold text-ink">{d.full_name}</p>
                        <p className="text-[12px] text-muted font-mono">{d.phone}</p>
                      </div>
                      <StatusBadge
                        status={d.status}
                        label={DRIVER_STATUS_LABEL[d.status] ?? d.status}
                      />
                    </div>
                  ))
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
