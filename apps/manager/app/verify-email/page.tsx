"use client";

import { CheckCircle2, MailCheck, Truck, AlertTriangle, ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Button } from "@/app/components/ui/Button";

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
        setError("Token de verificação inválido ou em falta.");
        return;
      }
      try {
        const res = await fetch("/api/onboarding/verify-email", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ token }),
        });
        const body = (await res.json()) as { error?: string };
        if (cancelled) return;
        
        if (!res.ok) {
          setStatus("error");
          setError(body.error || "Não foi possível confirmar o email.");
          return;
        }
        setStatus("success");
      } catch {
        if (!cancelled) {
          setStatus("error");
          setError("Falha de rede ao tentar validar o token.");
        }
      }
    }

    verify();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="flex flex-col items-center justify-center text-center mt-6">
      {status === "loading" && (
        <div className="flex flex-col items-center gap-4">
          <Loader2 size={48} className="text-indigo-600 animate-spin" />
          <p className="text-slate-600 font-medium">A confirmar o seu email, aguarde...</p>
        </div>
      )}
      
      {status === "success" && (
        <div className="flex flex-col items-center gap-6">
          <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center">
            <CheckCircle2 size={40} className="text-emerald-600" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-slate-900">Email Verificado!</h2>
            <p className="text-slate-500 font-medium mt-2">A sua conta está ativada. A sua instância isolada do ROTAS está totalmente operacional.</p>
          </div>
          <Link href="/">
            <Button className="h-12 px-8 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold flex items-center gap-2">
              Aceder ao Painel de Controlo <ArrowRight size={18} />
            </Button>
          </Link>
        </div>
      )}
      
      {status === "error" && (
        <div className="flex flex-col items-center gap-6">
          <div className="w-20 h-20 bg-rose-100 rounded-full flex items-center justify-center">
            <AlertTriangle size={40} className="text-rose-600" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-slate-900">Falha na Verificação</h2>
            <p className="text-slate-500 font-medium mt-2">{error}</p>
          </div>
          <Link href="/login">
            <Button variant="outline" className="h-12 px-8 border-slate-300 text-slate-700 hover:bg-slate-50 rounded-xl font-bold">
              Voltar ao Login
            </Button>
          </Link>
        </div>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-3xl p-8 shadow-xl shadow-slate-200/40 relative overflow-hidden">
        {/* Background Decoration */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-50 rounded-full blur-3xl"></div>
        
        <div className="relative z-10">
          <div className="flex flex-col items-center justify-center text-center mb-8">
            <div className="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-600/30 mb-4">
              <Truck size={32} className="text-white" />
            </div>
            <h1 className="text-xl font-black text-slate-900 tracking-tight">ROTAS Cloud</h1>
          </div>

          <Suspense fallback={<div className="flex justify-center p-8"><Loader2 className="animate-spin text-indigo-600" size={32} /></div>}>
            <VerifyEmailContent />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
