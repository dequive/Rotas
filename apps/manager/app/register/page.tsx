"use client";

import { Building2, Truck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const form = new FormData(e.currentTarget);
    try {
      const res = await fetch("/api/onboarding/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: form.get("company_name"),
          company_slug: form.get("company_slug") || undefined,
          company_nuit: form.get("company_nuit") || undefined,
          phone: form.get("phone") || undefined,
          owner_full_name: form.get("owner_full_name"),
          owner_email: form.get("owner_email"),
          owner_password: form.get("owner_password"),
        }),
      });
      const body = (await res.json()) as { error?: string; verificationUrl?: string };
      if (!res.ok || body.error) {
        setError(body.error ?? "Não foi possível concluir o registo.");
        return;
      }
      if (body.verificationUrl) {
        router.push(body.verificationUrl);
        router.refresh();
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
        <p className="login-subtitle">Criar conta da transportadora</p>
        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Empresa
            <input name="company_name" placeholder="Transportes Maputo Norte" required />
          </label>
          <label>
            Slug
            <input name="company_slug" placeholder="transportes-maputo-norte" />
          </label>
          <label>
            NUIT
            <input name="company_nuit" inputMode="numeric" placeholder="400000001" />
          </label>
          <label>
            Telefone
            <input name="phone" inputMode="tel" placeholder="258840000001" />
          </label>
          <label>
            Nome do owner
            <input name="owner_full_name" placeholder="Ana Manuel" required />
          </label>
          <label>
            Email do owner
            <input name="owner_email" type="email" placeholder="ana@empresa.co.mz" required />
          </label>
          <label>
            Palavra-passe
            <input
              name="owner_password"
              type="password"
              minLength={8}
              placeholder="••••••••"
              required
            />
          </label>
          {error && <p className="login-error">{error}</p>}
          <button type="submit" className="login-btn" disabled={loading}>
            <Building2 size={18} />
            {loading ? "A criar..." : "Criar conta"}
          </button>
        </form>
        <p className="login-subtitle">
          Já tem conta? <Link href="/login">Entrar</Link>
        </p>
      </div>
    </div>
  );
}
