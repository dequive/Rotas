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
  Settings,
  Truck,
  Users,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

type NavItem = {
  key: string;
  label: string;
  href: string;
  icon: typeof Truck;
};

type NavSection = {
  section: string;
  items: NavItem[];
};

// DESIGN.md mandated structure — grouped sections, never flat list
const NAV_SECTIONS: NavSection[] = [
  {
    section: "Operações",
    items: [
      { key: "operacao",           label: "Torre de Controlo", href: "/",                    icon: Map      },
      { key: "viagens",            label: "Viagens",           href: "/viagens",              icon: Route    },
      { key: "motoristas-despacho",label: "Despachos",         href: "/motoristas#despacho",  icon: FileText },
    ],
  },
  {
    section: "Frota",
    items: [
      { key: "viaturas",   label: "Viaturas",   href: "/viaturas",   icon: Truck  },
      { key: "motoristas", label: "Motoristas", href: "/motoristas", icon: Users  },
      { key: "manutencao", label: "Manutenção", href: "/manutencao", icon: Wrench },
    ],
  },
  {
    section: "Financeiro",
    items: [
      { key: "contratos", label: "Contratos", href: "/contratos",  icon: FileText    },
      { key: "cobranca",  label: "Cobrança",  href: "/#cobranca",  icon: ReceiptText },
      { key: "analytics", label: "Análise",   href: "/analytics",  icon: BarChart2   },
    ],
  },
  {
    section: "Config",
    items: [
      { key: "rotas-config", label: "Destinos",   href: "/rotas-config", icon: MapPin      },
      { key: "alertas",      label: "Alertas",    href: "/#alertas",     icon: AlertTriangle },
      { key: "settings",     label: "Definições", href: "/settings",     icon: Settings    },
    ],
  },
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
      <aside
        className="flex flex-col"
        style={{ background: "var(--sidebar-bg)" }}
      >
        {/* Logo */}
        <div className="px-5 py-5 flex-shrink-0">
          <span
            className="text-[20px] font-extrabold tracking-tight"
            style={{ color: "var(--sidebar-text-active)" }}
          >
            ROTAS
          </span>
        </div>

        {/* Navigation sections */}
        <nav
          className="flex-1 flex flex-col px-3 pb-3 overflow-y-auto"
          aria-label="Navegação principal"
        >
          {NAV_SECTIONS.map((section, sectionIdx) => (
            <div key={section.section}>
              {/* Section header */}
              <span
                className={cn(
                  "block px-2 pb-1 text-[10px] font-semibold uppercase tracking-widest",
                  sectionIdx === 0 ? "pt-2" : "pt-5"
                )}
                style={{ color: "var(--sidebar-section)" }}
              >
                {section.section}
              </span>

              {/* Section items */}
              <div className="flex flex-col gap-0.5">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = active === item.key;
                  return (
                    <Link
                      key={item.key}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] no-underline border-0 relative",
                        "transition-colors duration-100",
                        isActive
                          ? "border-l-2 border-amber pl-[10px]"
                          : "border-l-2 border-transparent pl-[10px]"
                      )}
                      style={{
                        color: isActive
                          ? "var(--sidebar-text-active)"
                          : "var(--sidebar-text)",
                        background: isActive
                          ? "var(--sidebar-active)"
                          : "transparent",
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive) {
                          (e.currentTarget as HTMLElement).style.background =
                            "var(--sidebar-hover)";
                          (e.currentTarget as HTMLElement).style.color =
                            "var(--sidebar-text-active)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive) {
                          (e.currentTarget as HTMLElement).style.background =
                            "transparent";
                          (e.currentTarget as HTMLElement).style.color =
                            "var(--sidebar-text)";
                        }
                      }}
                    >
                      <Icon size={15} className="flex-shrink-0" />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Logout button */}
        <div
          className="px-3 pb-5 flex-shrink-0 border-t"
          style={{ borderColor: "var(--sidebar-hover)" }}
        >
          <button
            className="mt-3 w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] border-0 bg-transparent cursor-pointer transition-colors duration-100"
            style={{ color: "var(--sidebar-text)" }}
            onClick={handleLogout}
            title="Sair da conta"
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background =
                "var(--sidebar-hover)";
              (e.currentTarget as HTMLElement).style.color =
                "var(--sidebar-text-active)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "transparent";
              (e.currentTarget as HTMLElement).style.color =
                "var(--sidebar-text)";
            }}
          >
            <LogOut size={15} className="flex-shrink-0" />
            <span>Sair</span>
          </button>
        </div>
      </aside>

      {/* Main content area */}
      <section className="min-w-0 bg-[var(--bg)]">
        <div className="p-6">{children}</div>
      </section>
    </main>
  );
}
