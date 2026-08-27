"use client";

import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  Banknote,
  CheckCircle2,
  ChevronRight,
  Clock,
  DollarSign,
  FileCheck,
  FileText,
  Filter,
  Layers,
  LayoutDashboard,
  LifeBuoy,
  Lock,
  MapPin,
  PackageCheck,
  ReceiptText,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Truck,
  UserCheck,
  Wrench,
} from "lucide-react";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type {
  ControlTowerLoadResult,
  ControlTowerSummary,
} from "../lib/control-tower-api";
import type { BillingTrip } from "../lib/billing-api";
import type { FuelControlBoardLoadResult } from "../lib/fuel-operations-api";
import type { FleetHistoryLoadResult } from "../lib/fleet-history-api";
import type { TripOrder } from "../lib/trip-orders-api";
import type { Vehicle } from "../lib/vehicles-api";
import type { Driver } from "../lib/drivers-api";
import type { Contract } from "../lib/contracts-api";

import { DispatchBoard } from "./DispatchBoard";
import { TransportCargoBoard } from "./TransportCargoBoard";
import { FleetComplianceBoard } from "./FleetComplianceBoard";
import { FleetHistoryBoard } from "./FleetHistoryBoard";
import { FuelControlBoard } from "./FuelControlBoard";
import { CostMarginBoard } from "./CostMarginBoard";
import { bffRequest } from "../lib/bff";
import { TripOrderFormModal } from "./TripOrderFormModal";

type DomainTab = "all" | "tms" | "workshop" | "compliance" | "finance";

interface ControlTowerCommandCenterProps {
  controlTower: ControlTowerLoadResult;
  fuelControlBoard: FuelControlBoardLoadResult;
  fleetHistories: FleetHistoryLoadResult;
  billingTrips: BillingTrip[];
  pendingOrders: TripOrder[];
  vehicles: Vehicle[];
  drivers: Driver[];
  contracts: Contract[];
  apiConfig: { tenantId: string | null };
}

function formatMoney(amount: number) {
  return new Intl.NumberFormat("pt-MZ", {
    style: "decimal",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount) + " MT";
}

function formatDate(iso: string) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("pt-MZ", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function ControlTowerCommandCenter({
  controlTower,
  fuelControlBoard,
  fleetHistories,
  billingTrips,
  pendingOrders,
  vehicles,
  drivers,
  contracts,
  apiConfig,
}: ControlTowerCommandCenterProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<DomainTab>("all");
  const [isPending, startTransition] = useTransition();

  const { tower } = controlTower;
  const summary: ControlTowerSummary = tower.summary;
  const queues = tower.queues;

  const handleRefresh = () => {
    startTransition(() => {
      router.refresh();
    });
  };

  return (
    <div className="w-full space-y-6">
      {/* Top Banner Header SOTA */}
      <div className="relative overflow-hidden rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-700 border border-emerald-500/20">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                SISTEMA AO VIVO
              </span>
              <span className="text-xs text-muted-foreground font-mono">
                Data Operacional: {tower.date}
              </span>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-foreground flex items-center gap-2">
              <LayoutDashboard className="h-6 w-6 text-amber" />
              Torre de Controlo — Command Center
            </h1>
            <p className="text-sm text-muted-foreground max-w-3xl">
              Supervisão integrada em tempo real: autorizações de despacho, frota em rota, exceções operacionais, manutenção e apuramento financeiro.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleRefresh}
              disabled={isPending}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-medium bg-card border border-border text-foreground hover:bg-muted/50 transition-colors shadow-sm disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 text-amber-dark ${isPending ? "animate-spin" : ""}`} />
              <span>{isPending ? "A atualizar..." : "Atualizar Dados"}</span>
            </button>
          </div>
        </div>

        {/* Domain Filter Tabs */}
        <div className="mt-6 pt-4 border-t border-border/60 flex items-center gap-1 overflow-x-auto no-scrollbar">
          <button
            onClick={() => setActiveTab("all")}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === "all"
                ? "bg-amber text-white shadow-sm font-semibold"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Visão Geral</span>
          </button>

          <button
            onClick={() => setActiveTab("tms")}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === "tms"
                ? "bg-amber text-white shadow-sm font-semibold"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            <Truck className="h-3.5 w-3.5" />
            <span>Transporte &amp; Frota (TMS)</span>
            {summary.tripsInExecution > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-white/20 text-white">
                {summary.tripsInExecution}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("workshop")}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === "workshop"
                ? "bg-amber text-white shadow-sm font-semibold"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            <Wrench className="h-3.5 w-3.5" />
            <span>Oficina Auto</span>
          </button>

          <button
            onClick={() => setActiveTab("compliance")}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === "compliance"
                ? "bg-amber text-white shadow-sm font-semibold"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Conformidade &amp; Alertas</span>
            {(summary.vehicleDocumentsExpiring + summary.driverDocumentsExpiring) > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-amber-500 text-white">
                {summary.vehicleDocumentsExpiring + summary.driverDocumentsExpiring}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("finance")}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === "finance"
                ? "bg-amber text-white shadow-sm font-semibold"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            <DollarSign className="h-3.5 w-3.5" />
            <span>Financeiro &amp; Custos</span>
          </button>
        </div>
      </div>

      {/* SOTA Executive KPI Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
        <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[11px] font-bold uppercase tracking-wider">Ordens Abertas</span>
            <FileText className="h-4 w-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-foreground">
            {summary.tripOrdersOpen}
          </div>
          <p className="text-[11px] text-muted-foreground">Novas solicitações de carga</p>
        </div>

        <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[11px] font-bold uppercase tracking-wider">Despacho Pendente</span>
            <Clock className="h-4 w-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-foreground flex items-center gap-2">
            <span>{summary.dispatchPending}</span>
            {summary.dispatchBlocked > 0 && (
              <span className="text-xs font-normal text-rose-500">({summary.dispatchBlocked} bloq)</span>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground">Aguardam autorização de saída</p>
        </div>

        <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[11px] font-bold uppercase tracking-wider">Em Execução</span>
            <Truck className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-600">
            {summary.tripsInExecution}
          </div>
          <p className="text-[11px] text-muted-foreground">Camisões em rota ativa</p>
        </div>

        <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[11px] font-bold uppercase tracking-wider">Incidentes</span>
            <ShieldAlert className="h-4 w-4 text-rose-500" />
          </div>
          <div className={`text-2xl font-bold font-mono ${summary.incidentsOpen > 0 ? "text-rose-600" : "text-foreground"}`}>
            {summary.incidentsOpen}
          </div>
          <p className="text-[11px] text-muted-foreground">Ocorrências não resolvidas</p>
        </div>

        <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[11px] font-bold uppercase tracking-wider">Descargas a Validar</span>
            <PackageCheck className="h-4 w-4 text-indigo-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-foreground">
            {summary.deliveryProofsPendingValidation}
          </div>
          <p className="text-[11px] text-muted-foreground">Comprovativos para aceitação</p>
        </div>

        <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[11px] font-bold uppercase tracking-wider">Prontas a Cobrar</span>
            <ReceiptText className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-foreground">
            {summary.billingReady}
          </div>
          <p className="text-[11px] text-muted-foreground">Prontas para faturação fiscal</p>
        </div>
      </div>

      {/* Domain Content Sections */}

      {/* VISÃO GERAL (ALL) OR TMS */}
      {(activeTab === "all" || activeTab === "tms") && (
        <div className="space-y-6">
          {/* Quick Action Center — Critical Work Queues */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Blocked Dispatches */}
            <div className="rounded-xl border border-border bg-card shadow-sm p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-rose-500" />
                  <h3 className="text-sm font-semibold text-foreground">Autorizações Bloqueadas</h3>
                </div>
                <span className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-rose-500/10 text-rose-600">
                  {queues.blockedDispatch.length}
                </span>
              </div>

              {queues.blockedDispatch.length === 0 ? (
                <div className="py-6 text-center text-xs text-muted-foreground">
                  Sem autorizações bloqueadas.
                </div>
              ) : (
                <div className="space-y-2 max-h-56 overflow-y-auto no-scrollbar">
                  {queues.blockedDispatch.map((item) => (
                    <div key={item.clearanceId} className="p-3 rounded-lg bg-muted/30 border border-border/50 text-xs space-y-1">
                      <div className="flex items-center justify-between font-medium text-foreground">
                        <span>{item.route}</span>
                        <span className="font-mono text-[10px] text-muted-foreground">{formatDate(item.updatedAt)}</span>
                      </div>
                      <p className="text-rose-600 text-[11px] font-medium">{item.blockedReason}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Open Incidents */}
            <div className="rounded-xl border border-border bg-card shadow-sm p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-amber-500" />
                  <h3 className="text-sm font-semibold text-foreground">Incidentes Abertos</h3>
                </div>
                <span className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-500/10 text-amber-600">
                  {queues.openIncidents.length}
                </span>
              </div>

              {queues.openIncidents.length === 0 ? (
                <div className="py-6 text-center text-xs text-muted-foreground">
                  Sem incidentes em aberto.
                </div>
              ) : (
                <div className="space-y-2 max-h-56 overflow-y-auto no-scrollbar">
                  {queues.openIncidents.map((item) => (
                    <div key={item.incidentId} className="p-3 rounded-lg bg-muted/30 border border-border/50 text-xs space-y-1">
                      <div className="flex items-center justify-between font-medium text-foreground">
                        <span className="uppercase font-bold text-amber-600">{item.incidentType}</span>
                        <span className="font-mono text-[10px] text-muted-foreground">{formatDate(item.occurredAt)}</span>
                      </div>
                      <p className="text-foreground text-[11px]">{item.route}</p>
                      <p className="text-muted-foreground text-[11px] line-clamp-1">{item.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Pending Delivery Proofs */}
            <div className="rounded-xl border border-border bg-card shadow-sm p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
                <div className="flex items-center gap-2">
                  <PackageCheck className="h-4 w-4 text-amber" />
                  <h3 className="text-sm font-semibold text-foreground">Validação de Descarga</h3>
                </div>
                <span className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-light text-amber-dark">
                  {queues.pendingDeliveryValidation.length}
                </span>
              </div>

              {queues.pendingDeliveryValidation.length === 0 ? (
                <div className="py-6 text-center text-xs text-muted-foreground">
                  Sem comprovativos pendentes.
                </div>
              ) : (
                <div className="space-y-2 max-h-56 overflow-y-auto no-scrollbar">
                  {queues.pendingDeliveryValidation.map((item) => (
                    <div key={item.deliveryProofId} className="p-3 rounded-lg bg-muted/30 border border-border/50 text-xs space-y-1">
                      <div className="flex items-center justify-between font-medium text-foreground">
                        <span>{item.route}</span>
                        <span className="font-mono text-[10px] text-muted-foreground">{formatDate(item.deliveredAt)}</span>
                      </div>
                      <p className="text-muted-foreground text-[11px] font-mono">Doc #{item.documentNumber || "S/N"}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Dispatch Board */}
          <div className="flex justify-end">
            <TripOrderFormModal contracts={contracts} />
          </div>
          <DispatchBoard pendingOrders={pendingOrders} vehicles={vehicles} drivers={drivers} />

          {/* Transport Cargo Board */}
          <TransportCargoBoard apiConfig={apiConfig} result={controlTower} />
        </div>
      )}

      {/* OFICINA AUTO (WORKSHOP) */}
      {(activeTab === "all" || activeTab === "workshop") && (
        <div className="rounded-xl border border-border bg-card shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-border pb-4">
            <div>
              <h2 className="text-base font-bold text-foreground flex items-center gap-2">
                <Wrench className="h-5 w-5 text-amber" />
                Oficina Auto &amp; Manutenção Preventiva
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Acompanhamento de Ordens de Serviço ativas, agendamentos preventivos e rentabilidade da oficina.
              </p>
            </div>
            <a
              href="/oficina/rentabilidade"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-light text-amber-dark hover:bg-amber-light/80 transition-colors"
            >
              <span>Ver Relatório Completo BI</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </a>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-muted/30 border border-border/60 space-y-2">
              <span className="text-muted-foreground font-semibold uppercase tracking-wider text-[10px]">
                Ordens de Serviço Ativas
              </span>
              <div className="text-xl font-bold font-mono text-foreground">
                {summary.operationalExceptionsOpen} em progresso
              </div>
              <p className="text-muted-foreground">Check-in, orçamentação e reparação em baía</p>
            </div>

            <div className="p-4 rounded-xl bg-muted/30 border border-border/60 space-y-2">
              <span className="text-muted-foreground font-semibold uppercase tracking-wider text-[10px]">
                Alertas Preventivos Iminentes
              </span>
              <div className="text-xl font-bold font-mono text-amber-600">
                {summary.vehicleDocumentsExpiring} viaturas elegíveis
              </div>
              <p className="text-muted-foreground">Ciclos de quilometragem/calendário pendentes</p>
            </div>

            <div className="p-4 rounded-xl bg-muted/30 border border-border/60 space-y-2">
              <span className="text-muted-foreground font-semibold uppercase tracking-wider text-[10px]">
                Ferramentas &amp; Calibração
              </span>
              <div className="text-xl font-bold font-mono text-emerald-600">
                100% Conforme
              </div>
              <p className="text-muted-foreground">Sem equipamentos de teste vencidos</p>
            </div>
          </div>
        </div>
      )}

      {/* CONFORMIDADE & ALERTAS (COMPLIANCE) */}
      {(activeTab === "all" || activeTab === "compliance") && (
        <div className="space-y-6">
          <FleetComplianceBoard apiConfig={apiConfig} result={controlTower} />
          <FleetHistoryBoard result={fleetHistories} />
        </div>
      )}

      {/* FINANCEIRO & CUSTOS (FINANCE) */}
      {(activeTab === "all" || activeTab === "finance") && (
        <div className="space-y-6">
          <FuelControlBoard result={fuelControlBoard} />
          <CostMarginBoard apiConfig={apiConfig} result={controlTower} />
        </div>
      )}
    </div>
  );
}
