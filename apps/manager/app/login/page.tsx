"use client";

import { Truck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaChallenge, setMfaChallenge] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const body = (await res.json()) as {
        error?: string;
        mfaRequired?: boolean;
        mfaChallenge?: string;
      };
      if (!res.ok || body.error) {
        setError(body.error ?? "Credenciais inválidas.");
        return;
      }
      if (body.mfaRequired && body.mfaChallenge) {
        setMfaChallenge(body.mfaChallenge);
        return;
      }
      router.push("/");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  async function handleMfaSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!mfaChallenge) return;
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/mfa/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ challengeToken: mfaChallenge, code: mfaCode }),
      });
      const body = (await res.json()) as { error?: string };
      if (!res.ok || body.error) {
        setError(body.error ?? "Código MFA inválido.");
        return;
      }
      router.push("/");
      router.refresh();
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
        <p className="login-subtitle">Gestão de frotas</p>
        <form onSubmit={mfaChallenge ? handleMfaSubmit : handleSubmit} className="login-form">
          {mfaChallenge ? (
            <label>
              Código MFA
              <input
                inputMode="numeric"
                pattern="[0-9]*"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                placeholder="123456"
                required
                autoComplete="one-time-code"
              />
            </label>
          ) : (
            <>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@rotas.local"
              required
              autoComplete="username"
            />
          </label>
          <label>
            Palavra-passe
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
            />
          </label>
          <p className="login-subtitle">
            <Link href="/forgot-password">Esqueceu a palavra-passe?</Link>
          </p>
            </>
          )}
          {error && <p className="login-error">{error}</p>}
          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? "A entrar..." : mfaChallenge ? "Confirmar" : "Entrar"}
          </button>
        </form>
        <p className="login-subtitle">
          Nova transportadora? <Link href="/register">Criar conta</Link>
        </p>
      </div>
    </div>
  );
}
