"use client";

import { KeyRound, Truck } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button } from "@/app/components/ui/Button";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [token, setToken] = useState(searchParams.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/password-reset/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      const body = (await res.json()) as { error?: string };
      if (!res.ok || body.error) {
        setError(body.error ?? "Não foi possível atualizar a palavra-passe.");
        return;
      }
      router.push("/login");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="login-form">
      <label>
        Token
        <input
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Cole o token recebido"
          required
          autoComplete="one-time-code"
        />
      </label>
      <label>
        Nova palavra-passe
        <input
          type="password"
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          required
          autoComplete="new-password"
        />
      </label>
      {error && <p className="login-error">{error}</p>}
      <Button type="submit" variant="primary" disabled={loading} className="w-full h-11 text-[15px] mt-1">
        <KeyRound size={18} />
        {loading ? "A atualizar..." : "Atualizar palavra-passe"}
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-brand">
          <Truck size={32} />
          <span>ROTAS</span>
        </div>
        <p className="login-subtitle">Definir nova palavra-passe</p>
        <Suspense fallback={null}>
          <ResetPasswordForm />
        </Suspense>
        <p className="login-subtitle">
          Voltar para <Link href="/login">login</Link>
        </p>
      </div>
    </div>
  );
}
