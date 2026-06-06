"use client";

import {
  AlertTriangle,
  BarChart2,
  ChevronLeft,
  ChevronRight,
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
import { useState } from "react";
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
  const [collapsed, setCollapsed] = useState(false);

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <main
      className="h-screen overflow-hidden grid"
      style={{ gridTemplateColumns: `${collapsed ? "56px" : "248px"} minmax(0, 1fr)` }}
    >
      <aside
        className="h-full flex flex-col overflow-hidden transition-all duration-150"
        style={{ background: "var(--sidebar-bg)" }}
      >
        {/* Logo + collapse toggle */}
        <div className="px-3 py-4 flex items-center justify-between flex-shrink-0">
          {!collapsed && (
            <span
              className="text-[20px] font-extrabold tracking-tight px-2"
              style={{ color: "var(--sidebar-text-active)" }}
            >
              ROTAS
            </span>
          )}
          <button
            onClick={() => setCollapsed((c) => !c)}
            className={cn(
              "flex items-center justify-center h-7 w-7 rounded-md border-0 bg-transparent cursor-pointer transition-colors duration-100 flex-shrink-0",
              collapsed && "mx-auto"
            )}
            style={{ color: "var(--sidebar-section)" }}
            title={collapsed ? "Expandir menu" : "Recolher menu"}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "var(--sidebar-hover)";
              (e.currentTarget as HTMLElement).style.color = "var(--sidebar-text-active)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "transparent";
              (e.currentTarget as HTMLElement).style.color = "var(--sidebar-section)";
            }}
          >
            {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
          </button>
        </div>

        {/* Navigation sections */}
        <nav
          className="flex-1 flex flex-col px-2 pb-3 overflow-y-auto overflow-x-hidden"
          aria-label="Navegação principal"
        >
          {NAV_SECTIONS.map((section, sectionIdx) => (
            <div key={section.section}>
              {/* Section label — hidden when collapsed */}
              {!collapsed && (
                <span
                  className={cn(
                    "block px-2 pb-1 text-[10px] font-semibold uppercase tracking-widest",
                    sectionIdx === 0 ? "pt-1" : "pt-5"
                  )}
                  style={{ color: "var(--sidebar-section)" }}
                >
                  {section.section}
                </span>
              )}
              {collapsed && sectionIdx > 0 && (
                <div className="my-2 mx-2 border-t" style={{ borderColor: "var(--sidebar-hover)" }} />
              )}

              {/* Section items */}
              <div className="flex flex-col gap-0.5">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = active === item.key;
                  return (
                    <Link
                      key={item.key}
                      href={item.href}
                      title={collapsed ? item.label : undefined}
                      className={cn(
                        "flex items-center rounded-md text-[13px] no-underline border-0 relative transition-colors duration-100",
                        collapsed
                          ? "justify-center h-9 w-9 mx-auto"
                          : "gap-2.5 px-3 py-2 border-l-2",
                        !collapsed && (isActive ? "border-amber pl-[10px]" : "border-transparent pl-[10px]")
                      )}
                      style={{
                        color: isActive ? "var(--sidebar-text-active)" : "var(--sidebar-text)",
                        background: isActive ? "var(--sidebar-active)" : "transparent",
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive) {
                          (e.currentTarget as HTMLElement).style.background = "var(--sidebar-hover)";
                          (e.currentTarget as HTMLElement).style.color = "var(--sidebar-text-active)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive) {
                          (e.currentTarget as HTMLElement).style.background = "transparent";
                          (e.currentTarget as HTMLElement).style.color = "var(--sidebar-text)";
                        }
                      }}
                    >
                      <Icon size={15} className="flex-shrink-0" />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Logout button */}
        <div
          className="px-2 pb-4 flex-shrink-0 border-t"
          style={{ borderColor: "var(--sidebar-hover)" }}
        >
          <button
            className={cn(
              "mt-3 flex items-center rounded-md text-[13px] border-0 bg-transparent cursor-pointer transition-colors duration-100",
              collapsed ? "justify-center h-9 w-9 mx-auto" : "w-full gap-2.5 px-3 py-2"
            )}
            style={{ color: "var(--sidebar-text)" }}
            onClick={handleLogout}
            title="Sair da conta"
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "var(--sidebar-hover)";
              (e.currentTarget as HTMLElement).style.color = "var(--sidebar-text-active)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "transparent";
              (e.currentTarget as HTMLElement).style.color = "var(--sidebar-text)";
            }}
          >
            <LogOut size={15} className="flex-shrink-0" />
            {!collapsed && <span>Sair</span>}
          </button>
        </div>
      </aside>

      {/* Main content area — independently scrollable */}
      <section className="min-w-0 h-full overflow-y-auto bg-[var(--bg)]">
        <div className="p-6">{children}</div>
      </section>
    </main>
  );
}
