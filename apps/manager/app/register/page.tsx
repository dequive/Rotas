"use client";

import { Building2, Truck, Briefcase, Mail, Lock, Phone, User as UserIcon, ArrowRight, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/app/components/ui/Button";

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
        credentials: "include",
        body: JSON.stringify({
          company_name: form.get("company_name"),
          company_slug: form.get("company_slug") || undefined,
          company_nuit: form.get("company_nuit") || undefined,
          phone: form.get("phone") || undefined,
          owner_full_name: form.get("owner_full_name"),
          owner_email: form.get("owner_email"),
          owner_password: form.get("owner_password"),
          timezone: "Africa/Maputo",
          currency: "MZN"
        }),
      });
      const body = (await res.json()) as {
        error?: string;
        verificationUrl?: string;
      };
      if (!res.ok) {
        setError(body.error || "Não foi possível concluir o registo.");
        return;
      }

      if (body.verificationUrl) {
        router.push(body.verificationUrl);
        return;
      }
      
      router.push("/");
      router.refresh();
    } catch {
      setError("Erro de rede. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row font-sans selection:bg-indigo-500 selection:text-white">
      {/* Left Column: Branding */}
      <div className="hidden md:flex flex-1 bg-indigo-900 p-12 flex-col justify-between relative overflow-hidden">
        {/* Abstract Background Design */}
        <div className="absolute top-[-20%] left-[-10%] w-[140%] h-[140%] bg-gradient-to-br from-indigo-600/30 via-indigo-900 to-slate-900 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-indigo-500/20 rounded-full blur-3xl" />
        
        <div className="relative z-10">
          <div className="flex items-center gap-3 text-white">
            <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-2xl">
              <Truck size={28} className="text-indigo-900" />
            </div>
            <span className="text-3xl font-black tracking-tight">ROTAS</span>
          </div>
          
          <div className="mt-24 max-w-lg">
            <h1 className="text-5xl font-black text-white leading-tight mb-6">
              A espinha dorsal da sua transportadora.
            </h1>
            <p className="text-lg text-indigo-200 font-medium leading-relaxed">
              Gestão de frotas, manutenção, contas a pagar e contabilidade PGC-NIRF. Tudo integrado, automatizado e a funcionar em tempo real.
            </p>
          </div>
        </div>

        <div className="relative z-10 flex gap-6 text-indigo-300 text-sm font-medium">
          <div className="flex items-center gap-2">
            <ShieldCheck size={20} className="text-emerald-400" />
            Isolamento de Dados Garantido
          </div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={20} className="text-emerald-400" />
            Certificado PGC-NIRF
          </div>
        </div>
      </div>

      {/* Right Column: Registration Form */}
      <div className="flex-1 flex items-center justify-center p-6 md:p-12 relative z-10 bg-white">
        <div className="w-full max-w-md">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-black text-slate-900 tracking-tight">Crie a sua conta</h2>
            <p className="text-slate-500 mt-2 font-medium">14 dias de teste grátis. Não requer cartão de crédito.</p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            {error && (
              <div className="bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3 rounded-xl text-sm font-medium shadow-sm">
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Company Info */}
              <div className="flex flex-col gap-1.5 md:col-span-2">
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">Nome da Transportadora</label>
                <div className="relative">
                  <Building2 size={18} className="absolute left-3 top-3 text-slate-400" />
                  <input 
                    name="company_name" required placeholder="Ex: Transportes Maputo Sul"
                    className="w-full h-12 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 outline-none transition-all font-medium text-slate-900 placeholder-slate-400"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">NUIT (Opcional)</label>
                <div className="relative">
                  <Briefcase size={18} className="absolute left-3 top-3 text-slate-400" />
                  <input 
                    name="company_nuit" placeholder="400000000" inputMode="numeric"
                    className="w-full h-12 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 outline-none transition-all font-medium text-slate-900 placeholder-slate-400"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">Telefone Sede</label>
                <div className="relative">
                  <Phone size={18} className="absolute left-3 top-3 text-slate-400" />
                  <input 
                    name="phone" placeholder="258 84 000 0000" inputMode="tel"
                    className="w-full h-12 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 outline-none transition-all font-medium text-slate-900 placeholder-slate-400"
                  />
                </div>
              </div>

              {/* Divider */}
              <div className="md:col-span-2 flex items-center gap-4 my-2">
                <div className="h-px bg-slate-100 flex-1"></div>
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Conta do Administrador</span>
                <div className="h-px bg-slate-100 flex-1"></div>
              </div>

              {/* Owner Info */}
              <div className="flex flex-col gap-1.5 md:col-span-2">
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">O seu Nome</label>
                <div className="relative">
                  <UserIcon size={18} className="absolute left-3 top-3 text-slate-400" />
                  <input 
                    name="owner_full_name" required placeholder="João Metical"
                    className="w-full h-12 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 outline-none transition-all font-medium text-slate-900 placeholder-slate-400"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5 md:col-span-2">
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">O seu Email</label>
                <div className="relative">
                  <Mail size={18} className="absolute left-3 top-3 text-slate-400" />
                  <input 
                    name="owner_email" type="email" required placeholder="joao@transportes.co.mz"
                    className="w-full h-12 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 outline-none transition-all font-medium text-slate-900 placeholder-slate-400"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5 md:col-span-2">
                <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">Palavra-passe Segura</label>
                <div className="relative">
                  <Lock size={18} className="absolute left-3 top-3 text-slate-400" />
                  <input 
                    name="owner_password" type="password" required minLength={8} placeholder="Mínimo 8 caracteres"
                    className="w-full h-12 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 outline-none transition-all font-medium text-slate-900 placeholder-slate-400"
                  />
                </div>
              </div>
            </div>

            <Button 
              type="submit" 
              disabled={loading} 
              className="w-full h-14 mt-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-base font-bold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 transition-all hover:shadow-indigo-600/40 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:transform-none"
            >
              {loading ? "A criar o seu Tenant..." : <><Building2 size={20} /> Aceder à Plataforma <ArrowRight size={20} /></>}
            </Button>
          </form>

          <p className="text-center mt-8 text-sm text-slate-500 font-medium">
            Já aderiu ao ROTAS? <Link href="/login" className="text-indigo-600 font-bold hover:underline">Iniciar Sessão</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
