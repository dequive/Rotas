"use client";

import { CheckCircle2, MailCheck, Truck } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function verify() {
      if (!token) {
        setStatus("error");
        setError("Token de verificação em falta.");
        return;
      }
      const res = await fetch("/api/onboarding/verify-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const body = (await res.json()) as { error?: string };
      if (cancelled) return;
      if (!res.ok || body.error) {
        setStatus("error");
        setError(body.error ?? "Não foi possível confirmar o email.");
        return;
      }
      setStatus("success");
    }

    verify();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="login-form">
      {status === "loading" && <p className="login-subtitle">A confirmar email...</p>}
      {status === "success" && (
        <>
          <p className="success-msg">
            <CheckCircle2 size={16} />
            Email confirmado com sucesso.
          </p>
          <Link
            className="inline-flex items-center justify-center font-bold rounded-lg h-[38px] px-[14px] text-sm bg-amber text-ink border border-amber hover:bg-amber-dark hover:border-amber-dark transition-colors duration-100 whitespace-nowrap"
            href="/"
          >
            Continuar
          </Link>
        </>
      )}
      {status === "error" && (
        <>
          <p className="login-error">{error}</p>
          <Link
            className="inline-flex items-center justify-center font-bold rounded-lg h-[38px] px-[14px] text-sm bg-surface text-ink border border-border hover:bg-surface-2 transition-colors duration-100 whitespace-nowrap"
            href="/login"
          >
            Voltar ao login
          </Link>
        </>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-brand">
          <Truck size={32} />
          <span>ROTAS</span>
        </div>
        <p className="login-subtitle">
          <MailCheck size={16} />
          Confirmação de email
        </p>
        <Suspense fallback={<p className="login-subtitle">A confirmar email...</p>}>
          <VerifyEmailContent />
        </Suspense>
      </div>
    </div>
  );
}
