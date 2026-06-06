"use client";

import {
  AlertTriangle,
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
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">ROTAS</div>
        <nav className="nav" aria-label="Navegacao principal">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.key}
                href={item.href}
                className={active === item.key ? "active" : ""}
              >
                <Icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <button className="logout-btn" onClick={handleLogout} title="Sair">
          <LogOut size={16} />
          Sair
        </button>
      </aside>
      <section className="main">{children}</section>
    </main>
  );
}
