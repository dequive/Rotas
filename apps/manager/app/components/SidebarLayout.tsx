"use client";

import {
  AlertTriangle,
  BarChart2,
  Bell,
  Building2,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  ClipboardCheck,
  ClipboardList,
  DollarSign,
  FileText,
  LogOut,
  Map,
  MapPin,
  Menu,
  ReceiptText,
  Route,
  Settings,
  ShieldCheck,
  Truck,
  Users,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { bffRequest } from "@/app/lib/bff";

type NavItem = {
  key: string;
  label: string;
  href: string;
  icon: typeof Truck;
};

type NavSection = {
  section: string;
  module?: "tms" | "oficina";
  items: NavItem[];
};

// DESIGN.md mandated structure — grouped sections, never flat list
const NAV_SECTIONS: NavSection[] = [
  {
    section: "Operações",
    module: "tms",
    items: [
      { key: "operacao",           label: "Torre de Controlo", href: "/",                    icon: Map      },
      { key: "tarefas",            label: "Central de Tarefas", href: "/tarefas",             icon: ClipboardList },
      { key: "viagens",            label: "Viagens",           href: "/viagens",              icon: Route    },
      { key: "despacho",           label: "Despacho",           href: "/despacho",             icon: FileText },
    ],
  },
  {
    section: "Frota",
    module: "tms",
    items: [
      { key: "viaturas",   label: "Viaturas",   href: "/viaturas",   icon: Truck     },
      { key: "motoristas", label: "Motoristas", href: "/motoristas", icon: Users     },
      { key: "manutencao", label: "Manutenção", href: "/manutencao", icon: Wrench   },
      { key: "terceiros",  label: "Terceiros",  href: "/terceiros",  icon: Building2 },
    ],
  },
  {
    section: "Oficina",
    module: "oficina",
    items: [
      { key: "recepcao",             label: "Recepção",       href: "/oficina",                     icon: ClipboardCheck },
      { key: "orcamentos",           label: "Orçamentos",     href: "/oficina/orcamentos",          icon: FileText       },
      { key: "os-oficina",           label: "Ordens Serviço", href: "/oficina/ordens-servico",      icon: Wrench         },
      { key: "pecas-oficina",        label: "Peças",          href: "/oficina/pecas",               icon: BookOpen       },
      { key: "faturacao-oficina",    label: "Faturação",      href: "/oficina/faturacao",           icon: ReceiptText    },
      { key: "rentabilidade-oficina",label: "Rentabilidade",  href: "/oficina/rentabilidade",       icon: BarChart2      },
      { key: "catalogo",             label: "Catálogo",       href: "/oficina/catalogo",            icon: BookOpen       },
      { key: "garantias",            label: "Garantias",      href: "/oficina/garantias",           icon: ShieldCheck    },
    ],
  },
  {
    section: "Financeiro",
    items: [
      { key: "clientes",  label: "Clientes",  href: "/clientes",   icon: Building2   },
      { key: "contratos", label: "Contratos", href: "/contratos",  icon: FileText    },
      { key: "cobranca",  label: "Cobrança",        href: "/cobranca",   icon: ReceiptText },
      { key: "ar",        label: "Contas a Receber", href: "/ar",         icon: DollarSign  },
      { key: "analytics", label: "Análise",          href: "/analytics",  icon: BarChart2   },
    ],
  },
  {
    section: "Config",
    items: [
      { key: "empresa",      label: "Empresa",    href: "/empresa",      icon: Building2   },
      { key: "rotas-config", label: "Destinos",   href: "/rotas-config", icon: MapPin      },
      { key: "alertas",        label: "Alertas",        href: "/alertas",        icon: AlertTriangle },
      { key: "notificacoes",   label: "Notificações",   href: "/notificacoes",   icon: Bell          },
      { key: "security",       label: "Segurança",      href: "/security",       icon: ShieldCheck   },
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
  const [mobileOpen, setMobileOpen] = useState(false);
  const [tenantModules, setTenantModules] = useState<string[]>(["tms", "oficina"]);

  useEffect(() => {
    bffRequest("/api/v1/tenants/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.product_modules) {
          setTenantModules(data.product_modules);
        }
      })
      .catch(() => {});
  }, []);

  const visibleSections = NAV_SECTIONS.filter(
    (sec) => !sec.module || tenantModules.includes(sec.module)
  );

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <>
      <a
        href="#main-content"
        className="skip-link"
      >
        Saltar para o conteúdo principal
      </a>
      <div
      className={cn(
        "h-dvh overflow-hidden bg-bg lg:grid",
        collapsed
          ? "lg:grid-cols-[56px_minmax(0,1fr)]"
          : "lg:grid-cols-[248px_minmax(0,1fr)]",
      )}
    >
      {mobileOpen && (
        <button
          type="button"
          aria-label="Fechar navegação"
          className="fixed inset-0 z-40 border-0 bg-rotas-950/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex h-full w-[min(88vw,320px)] flex-col overflow-hidden bg-sidebar-bg shadow-design-lg transition-transform duration-150",
          "lg:static lg:z-auto lg:w-auto lg:translate-x-0 lg:shadow-none",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
        style={{ background: "var(--sidebar-bg)" }}
      >
        {/* Logo + collapse toggle */}
        <div className="px-3 py-4 flex items-center justify-between flex-shrink-0">
          {(!collapsed || mobileOpen) && (
            <span
              className="text-[20px] font-extrabold tracking-tight px-2"
              style={{ color: "var(--sidebar-text-active)" }}
            >
              ROTAS
            </span>
          )}
          <button
            onClick={() => setCollapsed((c) => !c)}
            type="button"
            aria-label={collapsed ? "Expandir menu" : "Recolher menu"}
            aria-expanded={!collapsed}
            className={cn(
              "hidden items-center justify-center h-8 w-8 rounded-[var(--r-md)] border-0 bg-transparent cursor-pointer transition-colors duration-100 flex-shrink-0 lg:flex",
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
          <button
            type="button"
            aria-label="Fechar menu"
            className="flex h-11 w-11 items-center justify-center rounded-[var(--r-md)] border-0 bg-transparent text-sidebar-text hover:bg-sidebar-hover hover:text-sidebar-text-active lg:hidden"
            onClick={() => setMobileOpen(false)}
          >
            <X aria-hidden="true" size={20} />
          </button>
        </div>

        {/* Navigation sections */}
        <nav
          className="flex-1 flex flex-col px-2 pb-3 overflow-y-auto overflow-x-hidden"
          aria-label="Navegação principal"
        >
          {visibleSections.map((section, sectionIdx) => (
            <div key={section.section}>
              {/* Section label — hidden when collapsed */}
              {(!collapsed || mobileOpen) && (
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
              {collapsed && !mobileOpen && sectionIdx > 0 && (
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
                      onClick={() => setMobileOpen(false)}
                      className={cn(
                        "flex items-center rounded-md text-[13px] no-underline border-0 relative transition-colors duration-100",
                        collapsed && !mobileOpen
                          ? "justify-center h-9 w-9 mx-auto"
                          : "min-h-11 gap-2.5 px-3 py-2 border-l-2 lg:min-h-9",
                        (!collapsed || mobileOpen) && (isActive ? "border-rotas-400 pl-[10px]" : "border-transparent pl-[10px]")
                      )}
                      style={{
                        color: isActive ? "var(--sidebar-text-active)" : "var(--sidebar-text)",
                        background: isActive ? "var(--sidebar-active)" : "transparent",
                      }}
                      onMouseEnter={(e: React.MouseEvent<HTMLAnchorElement>) => {
                        if (!isActive) {
                          (e.currentTarget as HTMLElement).style.background = "var(--sidebar-hover)";
                          (e.currentTarget as HTMLElement).style.color = "var(--sidebar-text-active)";
                        }
                      }}
                      onMouseLeave={(e: React.MouseEvent<HTMLAnchorElement>) => {
                        if (!isActive) {
                          (e.currentTarget as HTMLElement).style.background = "transparent";
                          (e.currentTarget as HTMLElement).style.color = "var(--sidebar-text)";
                        }
                      }}
                    >
                      <Icon size={15} className="flex-shrink-0" />
                      {(!collapsed || mobileOpen) && <span className="truncate">{item.label}</span>}
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
              collapsed && !mobileOpen ? "justify-center h-9 w-9 mx-auto" : "min-h-11 w-full gap-2.5 px-3 py-2 lg:min-h-9"
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
            {(!collapsed || mobileOpen) && <span>Sair</span>}
          </button>
        </div>
      </aside>

      {/* Main content area — independently scrollable */}
      <main
        id="main-content"
        tabIndex={-1}
        className="min-w-0 h-full overflow-y-auto bg-bg"
      >
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-surface/95 px-4 backdrop-blur lg:hidden">
          <button
            type="button"
            aria-label="Abrir navegação"
            aria-expanded={mobileOpen}
            className="flex h-11 w-11 items-center justify-center rounded-[var(--r-md)] border border-border bg-surface text-ink"
            onClick={() => setMobileOpen(true)}
          >
            <Menu aria-hidden="true" size={20} />
          </button>
          <span className="font-semibold tracking-tight text-ink">ROTAS</span>
          <span aria-hidden="true" className="h-11 w-11" />
        </header>
        <div className="p-4 sm:p-6">{children}</div>
      </main>
      </div>
    </>
  );
}
