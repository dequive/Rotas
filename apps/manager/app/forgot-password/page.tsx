"use client";

import { KeyRound, Mail, Truck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [resetUrl, setResetUrl] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResetUrl(null);
    setSent(false);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/password-reset/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          tenant_slug: tenantSlug.trim() || undefined,
        }),
      });
      const body = (await res.json()) as {
        error?: string;
        resetToken?: string;
        resetUrl?: string;
      };
      if (!res.ok || body.error) {
        setError(body.error ?? "Não foi possível iniciar a recuperação.");
        return;
      }
      setSent(true);
      setResetUrl(body.resetUrl ?? (body.resetToken ? `/reset-password?token=${body.resetToken}` : null));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-brand">
          <Truck size={32} />
          <span>ROTAS</span>
        </div>
        <p className="login-subtitle">Recuperar acesso</p>
        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ana@empresa.co.mz"
              required
              autoComplete="username"
            />
          </label>
          <label>
            Slug da empresa
            <input
              value={tenantSlug}
              onChange={(e) => setTenantSlug(e.target.value)}
              placeholder="transportes-maputo-norte"
              autoComplete="organization"
            />
          </label>
          {error && <p className="login-error">{error}</p>}
          {sent && (
            <p className="success-msg">
              Pedido recebido. Se a conta existir, enviaremos as instruções de recuperação.
            </p>
          )}
          {resetUrl && (
            <Link className="secondary-btn" href={resetUrl}>
              <KeyRound size={16} />
              Abrir link local de recuperação
            </Link>
          )}
          <button type="submit" className="login-btn" disabled={loading}>
            <Mail size={18} />
            {loading ? "A enviar..." : "Enviar instruções"}
          </button>
        </form>
        <p className="login-subtitle">
          Lembrou-se? <Link href="/login">Entrar</Link>
        </p>
      </div>
    </div>
  );
}
