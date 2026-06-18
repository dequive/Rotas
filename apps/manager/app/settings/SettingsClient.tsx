"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { User, ShieldCheck, Settings, Zap } from "lucide-react";
import { SectionHeader } from "@/app/components/ui/SectionHeader";
import type { TenantLimits } from "@/app/components/LimitWarningBanner";
import { updateUserProfile } from "./actions";

interface Props {
  userId: string;
  userRole: string;
  initialName: string;
  initialEmail: string;
  initialPhone: string;
  limits: TenantLimits | null;
}

export function SettingsClient({
  userId,
  userRole,
  initialName,
  initialEmail,
  initialPhone,
  limits,
}: Props) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"perfil" | "acessos" | "preferencias">("perfil");
  
  const [fullName, setFullName] = useState(initialName);
  const [email, setEmail] = useState(initialEmail);
  const [phone, setPhone] = useState(initialPhone || "");
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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

        {activeTab === "acessos" && (
          <section className="bg-surface border border-border rounded-lg p-6">
            <SectionHeader title="Gestão de Acessos" />
            <div className="mt-6 flex flex-col items-center justify-center h-32 gap-3 bg-surface-2 border border-dashed border-border rounded-lg">
              <ShieldCheck size={24} className="text-muted" />
              <p className="text-[13px] text-muted font-semibold">Em breve</p>
              <p className="text-[12px] text-muted text-center max-w-xs">
                A gestão de utilizadores e permissões de acesso estará disponível numa próxima versão.
              </p>
            </div>
          </section>
        )}

        {activeTab === "preferencias" && (
          <section className="bg-surface border border-border rounded-lg p-6">
            <SectionHeader title="Preferências do Sistema" />
            <div className="mt-6 flex flex-col items-center justify-center h-32 gap-3 bg-surface-2 border border-dashed border-border rounded-lg">
              <Settings size={24} className="text-muted" />
              <p className="text-[13px] text-muted font-semibold">Em breve</p>
              <p className="text-[12px] text-muted text-center max-w-xs">
                Configurações de fuso horário, moeda e alertas por SMS/Email estarão disponíveis em breve.
              </p>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
