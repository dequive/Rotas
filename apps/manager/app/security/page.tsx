"use client";

import { RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { Button } from "@/app/components/ui/Button";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { PageHeader } from "@/app/components/ui/PageHeader";

type SessionItem = {
  id: string;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
  created_by_ip: string | null;
  user_agent: string | null;
  active: boolean;
};

type MfaStatus = {
  enabled: boolean;
  confirmed_at: string | null;
  secret?: string | null;
  otpauth_uri?: string | null;
};

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pt-MZ", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function browserLabel(userAgent: string | null) {
  if (!userAgent) return "Dispositivo não identificado";
  if (userAgent.includes("Edg/")) return "Microsoft Edge";
  if (userAgent.includes("Chrome/")) return "Chrome";
  if (userAgent.includes("Firefox/")) return "Firefox";
  if (userAgent.includes("Safari/")) return "Safari";
  return userAgent.slice(0, 80);
}

export default function SecurityPage() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [mfa, setMfa] = useState<MfaStatus | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [mfaBusy, setMfaBusy] = useState(false);

  async function loadSessions() {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/sessions", { cache: "no-store" });
      const body = (await res.json()) as SessionItem[] | { error?: string };
      if (!res.ok || !Array.isArray(body)) {
        setError(!Array.isArray(body) ? body.error ?? "Não foi possível carregar sessões." : "Erro.");
        return;
      }
      setSessions(body);
    } finally {
      setLoading(false);
    }
  }

  async function loadMfa() {
    const res = await fetch("/api/auth/mfa", { cache: "no-store" });
    const body = (await res.json()) as MfaStatus | { error?: string };
    if (res.ok && "enabled" in body) setMfa(body);
  }

  async function revokeSession(sessionId: string) {
    setBusyId(sessionId);
    setError(null);
    try {
      const res = await fetch(`/api/auth/sessions/${sessionId}`, { method: "DELETE" });
      const body = (await res.json()) as { error?: string };
      if (!res.ok || body.error) {
        setError(body.error ?? "Não foi possível revogar a sessão.");
        return;
      }
      await loadSessions();
    } finally {
      setBusyId(null);
    }
  }

  async function startMfaSetup() {
    setMfaBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/mfa/setup", { method: "POST" });
      const body = (await res.json()) as MfaStatus | { error?: string };
      if (!res.ok || !("enabled" in body)) {
        setError(!("enabled" in body) ? body.error ?? "Não foi possível iniciar MFA." : "Erro.");
        return;
      }
      setMfa(body);
    } finally {
      setMfaBusy(false);
    }
  }

  async function confirmMfa(e: React.FormEvent) {
    e.preventDefault();
    setMfaBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/mfa/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: mfaCode }),
      });
      const body = (await res.json()) as MfaStatus | { error?: string };
      if (!res.ok || !("enabled" in body)) {
        setError(!("enabled" in body) ? body.error ?? "Código MFA inválido." : "Erro.");
        return;
      }
      setMfaCode("");
      setMfa(body);
    } finally {
      setMfaBusy(false);
    }
  }

  async function disableMfa(e: React.FormEvent) {
    e.preventDefault();
    setMfaBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/mfa", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: disableCode }),
      });
      const body = (await res.json()) as MfaStatus | { error?: string };
      if (!res.ok || !("enabled" in body)) {
        setError(!("enabled" in body) ? body.error ?? "Código MFA inválido." : "Erro.");
        return;
      }
      setDisableCode("");
      setMfa(body);
    } finally {
      setMfaBusy(false);
    }
  }

  useEffect(() => {
    loadSessions();
    loadMfa();
  }, []);

  return (
    <SidebarLayout active="security">
      <PageHeader
        title="Segurança"
        eyebrow="Config"
        description="Sessões e acessos da conta"
        actions={
          <Button variant="secondary" onClick={loadSessions} disabled={loading}>
            <RefreshCw size={16} />
            Atualizar
          </Button>
        }
      />

      <section className="bg-surface border border-border rounded-lg p-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-base font-semibold m-0">Autenticação multifator</h2>
          <span>{mfa?.enabled ? "Ativa" : "Inativa"}</span>
        </div>
        <div className="modal-form">
          {mfa?.enabled ? (
            <form onSubmit={disableMfa} className="flex items-center gap-1.5">
              <input
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)}
                inputMode="numeric"
                placeholder="Código MFA"
                required
              />
              <Button variant="secondary" disabled={mfaBusy}>
                Desativar MFA
              </Button>
            </form>
          ) : mfa?.secret ? (
            <form onSubmit={confirmMfa} className="modal-form">
              <label>
                Segredo
                <input value={mfa.secret} readOnly />
              </label>
              <label>
                URI
                <input value={mfa.otpauth_uri ?? ""} readOnly />
              </label>
              <div className="flex items-center gap-1.5">
                <input
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value)}
                  inputMode="numeric"
                  placeholder="Código de 6 dígitos"
                  required
                />
                <Button variant="primary" disabled={mfaBusy}>
                  Confirmar MFA
                </Button>
              </div>
            </form>
          ) : (
            <Button variant="primary" onClick={startMfaSetup} disabled={mfaBusy}>
              <ShieldCheck size={16} />
              Ativar MFA
            </Button>
          )}
        </div>
      </section>

      <section className="bg-surface border border-border rounded-lg p-4 mt-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-base font-semibold m-0">Sessões</h2>
          <span>{sessions.filter((session) => session.active).length} ativas</span>
        </div>
        {error && <p className="text-error text-[13px] m-0 bg-error-bg border border-error-border rounded-md px-3 py-2">{error}</p>}
        {loading ? (
          <p className="py-2 text-muted text-sm">A carregar sessões...</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Estado</th>
                  <th>Dispositivo</th>
                  <th>IP</th>
                  <th>Criada</th>
                  <th>Expira</th>
                  <th>Revogada</th>
                  <th>Ação</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={session.id}>
                    <td>
                      <StatusBadge
                        status={session.active ? "activo" : "inactivo"}
                        label={session.active ? "Ativa" : "Inativa"}
                      />
                    </td>
                    <td className="inline-flex items-center gap-1.5">
                      <ShieldCheck size={15} />
                      {browserLabel(session.user_agent)}
                    </td>
                    <td>{session.created_by_ip ?? "—"}</td>
                    <td>{formatDate(session.created_at)}</td>
                    <td>{formatDate(session.expires_at)}</td>
                    <td>{formatDate(session.revoked_at)}</td>
                    <td>
                      <button
                        className="inline-flex items-center gap-1 h-[30px] px-2.5 bg-surface text-ink border border-border rounded-md text-xs font-bold whitespace-nowrap cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                        disabled={!session.active || busyId === session.id}
                        onClick={() => revokeSession(session.id)}
                      >
                        <XCircle size={14} />
                        Revogar
                      </button>
                    </td>
                  </tr>
                ))}
                {sessions.length === 0 && (
                  <tr>
                    <td className="text-muted text-center py-6" colSpan={7}>
                      Sem sessões registadas.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </SidebarLayout>
  );
}
