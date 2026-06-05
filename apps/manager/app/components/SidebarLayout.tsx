"use client";

import {
  AlertTriangle,
  BarChart2,
  FileText,
  LogOut,
  Map,
  MapPin,
  ReceiptText,
  Route,
  Truck,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

type NavItem = {
  key: string;
  label: string;
  href: string;
  icon: typeof Truck;
};

const NAV_ITEMS: NavItem[] = [
  { key: "operacao", label: "Operação", href: "/", icon: Map },
  { key: "viaturas", label: "Viaturas", href: "/viaturas", icon: Truck },
  { key: "motoristas", label: "Motoristas", href: "/motoristas", icon: Users },
  { key: "viagens", label: "Viagens", href: "/viagens", icon: Route },
  { key: "analytics", label: "Análise", href: "/analytics", icon: BarChart2 },
  { key: "contratos", label: "Contratos", href: "/contratos", icon: FileText },
  { key: "rotas-config", label: "Destinos", href: "/rotas-config", icon: MapPin },
  { key: "cobranca", label: "Cobrança", href: "/#cobranca", icon: ReceiptText },
  { key: "alertas", label: "Alertas", href: "/#alertas", icon: AlertTriangle },
];

export function SidebarLayout({
  children,
  active,
}: {
  children: React.ReactNode;
  active: string;
}) {
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <main className="min-h-screen grid grid-cols-[248px_minmax(0,1fr)]">
      <aside className="bg-nav text-white p-5 flex flex-col">
        <div className="text-[22px] font-extrabold mb-7 tracking-normal">ROTAS</div>
        <nav className="grid gap-1.5 flex-1" aria-label="Navegacao principal">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = active === item.key;
            return (
              <Link
                key={item.key}
                href={item.href}
                className={
                  "text-[#d9e4f2] bg-transparent no-underline px-3 py-2.5 rounded-md flex items-center gap-2 text-sm border-0 hover:bg-white/[0.12] hover:text-white" +
                  (isActive ? " bg-white/[0.12] text-white" : "")
                }
              >
                <Icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <button
          className="mt-auto pt-5 w-full border-0 text-[#d9e4f2] bg-transparent flex items-center gap-2 px-3 py-2.5 rounded-md text-sm cursor-pointer hover:bg-white/[0.12]"
          onClick={handleLogout}
          title="Sair"
        >
          <LogOut size={16} />
          Sair
        </button>
      </aside>
      <section className="min-w-0 p-6">{children}</section>
    </main>
  );
}
