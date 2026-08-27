"use client";

import type { LucideIcon } from "lucide-react";
import {
  CheckCircle2,
  CircleDollarSign,
  ClipboardCheck,
  Clock3,
  FileText,
  LockKeyhole,
  Search,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";

import { cn } from "@/lib/utils";

type Tone =
  | "reception"
  | "diagnosis"
  | "awaiting"
  | "supplement"
  | "execution"
  | "quality"
  | "delivered"
  | "cancelled"
  | "draft";

type StatusDefinition = {
  label: string;
  tone: Tone;
  icon: LucideIcon;
};

const statusConfig: Record<string, StatusDefinition> = {
  recebido: { label: "Recebido", tone: "reception", icon: ClipboardCheck },
  received: { label: "Recebido", tone: "reception", icon: ClipboardCheck },
  reception: { label: "Recepção", tone: "reception", icon: ClipboardCheck },
  em_diagnostico: { label: "Em diagnóstico", tone: "diagnosis", icon: Search },
  diagnostico_concluido: { label: "Diagnóstico concluído", tone: "diagnosis", icon: CheckCircle2 },
  aguardando_aprovacao: { label: "Aguardando aprovação", tone: "awaiting", icon: Clock3 },
  sent: { label: "Aguardando aprovação", tone: "awaiting", icon: Clock3 },
  supplemental: { label: "Orçamento adicional", tone: "supplement", icon: FileText },
  orcamento_adicional: { label: "Orçamento adicional", tone: "supplement", icon: FileText },
  aprovado: { label: "Aprovado", tone: "execution", icon: LockKeyhole },
  approved: { label: "Aprovado", tone: "execution", icon: LockKeyhole },
  accepted: { label: "Aprovado", tone: "execution", icon: LockKeyhole },
  em_execucao: { label: "Em execução", tone: "execution", icon: Wrench },
  in_service: { label: "Em serviço", tone: "execution", icon: Wrench },
  in_progress: { label: "Em execução", tone: "execution", icon: Wrench },
  execucao_concluida: { label: "Execução concluída", tone: "execution", icon: CheckCircle2 },
  quality_check: { label: "Controlo de qualidade", tone: "quality", icon: ShieldCheck },
  qc_concluido: { label: "QC concluído", tone: "quality", icon: ShieldCheck },
  ready: { label: "Pronto para entrega", tone: "quality", icon: ShieldCheck },
  faturado: { label: "Faturado", tone: "delivered", icon: CircleDollarSign },
  billed: { label: "Faturado", tone: "delivered", icon: CircleDollarSign },
  issued: { label: "Emitida", tone: "delivered", icon: CircleDollarSign },
  entregue: { label: "Entregue", tone: "delivered", icon: CheckCircle2 },
  delivered: { label: "Entregue", tone: "delivered", icon: CheckCircle2 },
  converted: { label: "Convertido em OS", tone: "delivered", icon: LockKeyhole },
  closed: { label: "Concluída", tone: "delivered", icon: CheckCircle2 },
  completed: { label: "Concluída", tone: "delivered", icon: CheckCircle2 },
  concluida: { label: "Concluída", tone: "delivered", icon: CheckCircle2 },
  em_rota: { label: "Em rota", tone: "execution", icon: Wrench },
  "em-rota": { label: "Em rota", tone: "execution", icon: Wrench },
  em_viagem: { label: "Em viagem", tone: "execution", icon: Wrench },
  cancelado: { label: "Cancelado", tone: "cancelled", icon: XCircle },
  cancelled: { label: "Cancelado", tone: "cancelled", icon: XCircle },
  cancelada: { label: "Cancelada", tone: "cancelled", icon: XCircle },
  rejected: { label: "Recusado", tone: "cancelled", icon: XCircle },
  returned_no_service: { label: "Devolvido sem serviço", tone: "cancelled", icon: XCircle },
  recusado: { label: "Recusado", tone: "cancelled", icon: XCircle },
  blocked: { label: "Bloqueado", tone: "cancelled", icon: XCircle },
  expired: { label: "Vencido", tone: "cancelled", icon: XCircle },
  billing_failed: { label: "Falha de faturação", tone: "cancelled", icon: XCircle },
  billing_pending: { label: "Faturação pendente", tone: "awaiting", icon: Clock3 },
  draft_created: { label: "Rascunho fiscal", tone: "diagnosis", icon: FileText },
  not_required: { label: "Não aplicável", tone: "draft", icon: FileText },
  draft: { label: "Rascunho", tone: "draft", icon: FileText },
  rascunho: { label: "Rascunho", tone: "draft", icon: FileText },
  open: { label: "Aberta", tone: "diagnosis", icon: ClipboardCheck },
  pending: { label: "Pendente", tone: "awaiting", icon: Clock3 },
  awaiting: { label: "Aguardando", tone: "awaiting", icon: Clock3 },
  paragem: { label: "Paragem", tone: "awaiting", icon: Clock3 },
  descarga: { label: "Descarga", tone: "supplement", icon: ClipboardCheck },
  alerta: { label: "Alerta", tone: "cancelled", icon: XCircle },
  aguarda: { label: "Expedida", tone: "diagnosis", icon: Clock3 },
  planeada: { label: "Planeada", tone: "draft", icon: FileText },
  manutencao: { label: "Em manutenção", tone: "awaiting", icon: Wrench },
  billable: { label: "A cobrar", tone: "diagnosis", icon: CircleDollarSign },
  not_billable: { label: "Não faturável", tone: "draft", icon: CircleDollarSign },
  waiver_required: { label: "Necessita dispensa", tone: "awaiting", icon: ShieldCheck },
  valid: { label: "Válido", tone: "delivered", icon: CheckCircle2 },
  expiring_soon: { label: "A vencer", tone: "awaiting", icon: Clock3 },
  activo: { label: "Activo", tone: "delivered", icon: CheckCircle2 },
  active: { label: "Ativa", tone: "delivered", icon: CheckCircle2 },
  claimed: { label: "Acionada", tone: "awaiting", icon: ShieldCheck },
  inactivo: { label: "Inactivo", tone: "cancelled", icon: XCircle },
};

const softToneClasses: Record<Tone, string> = {
  reception: "bg-status-reception-soft text-status-reception",
  diagnosis: "bg-status-diagnosis-soft text-status-diagnosis",
  awaiting: "bg-status-awaiting-soft text-status-awaiting",
  supplement: "bg-status-supplement-soft text-status-supplement",
  execution: "bg-status-execution-soft text-status-execution",
  quality: "bg-status-quality-soft text-status-quality",
  delivered: "bg-status-delivered-soft text-status-delivered",
  cancelled: "bg-status-cancelled-soft text-status-cancelled",
  draft: "bg-status-draft-soft text-status-draft",
};

const solidToneClasses: Record<Tone, string> = {
  reception: "bg-status-reception text-white",
  diagnosis: "bg-status-diagnosis text-white",
  awaiting: "bg-status-awaiting text-white",
  supplement: "bg-status-supplement text-white",
  execution: "bg-status-execution text-white",
  quality: "bg-status-quality text-white",
  delivered: "bg-status-delivered text-white",
  cancelled: "bg-status-cancelled text-white",
  draft: "bg-status-draft text-white",
};

export type StatusKey = keyof typeof statusConfig;

export function StatusBadge({
  status,
  label,
  variant = "soft",
  size = "sm",
  icon: IconOverride,
  className,
}: {
  status: StatusKey | string;
  label?: string;
  variant?: "solid" | "soft";
  size?: "sm" | "md";
  icon?: LucideIcon;
  className?: string;
}) {
  const normalizedStatus = status.trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  const definition = statusConfig[normalizedStatus] ?? {
    label: status.replaceAll("_", " "),
    tone: "draft" as const,
    icon: FileText,
  };
  const Icon = IconOverride ?? definition.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-[var(--r-full)] font-semibold",
        size === "sm" ? "gap-1.5 px-2 py-1 text-xs" : "gap-2 px-2.5 py-1.5 text-[13px]",
        variant === "solid" ? solidToneClasses[definition.tone] : softToneClasses[definition.tone],
        className,
      )}
    >
      <Icon aria-hidden="true" className={size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"} />
      <span className="capitalize">{label ?? definition.label}</span>
    </span>
  );
}
