"use client";

import { cn } from '@/lib/utils'

// Complete status map — covers all entity states across the application.
// Keys match the status strings returned by the API.
const statusConfig = {
  // ── Trip / vehicle operational statuses ──────────────
  'em-rota':        { label: 'Em Rota',          dot: 'bg-success',  bg: 'bg-success-bg',  text: 'text-success' },
  'em_viagem':      { label: 'Em Viagem',         dot: 'bg-amber',    bg: 'bg-amber-light', text: 'text-amber-dark' },
  'paragem':        { label: 'Paragem',            dot: 'bg-warning',  bg: 'bg-warning-bg',  text: 'text-warning' },
  'descarga':       { label: 'Descarga',           dot: 'bg-amber',    bg: 'bg-amber-light', text: 'text-amber-dark' },
  'alerta':         { label: 'Alerta',             dot: 'bg-error',    bg: 'bg-error-bg',    text: 'text-error' },
  'aguarda':        { label: 'Expedida',           dot: 'bg-info',     bg: 'bg-info-bg',     text: 'text-info' },
  'concluida':      { label: 'Concluída',          dot: 'bg-success',  bg: 'bg-success-bg',  text: 'text-success' },
  'cancelada':      { label: 'Cancelada',          dot: 'bg-error',    bg: 'bg-error-bg',    text: 'text-error' },
  'planeada':       { label: 'Planeada',           dot: 'bg-info',     bg: 'bg-info-bg',     text: 'text-info' },
  'manutencao':     { label: 'Em Manutenção',      dot: 'bg-warning',  bg: 'bg-warning-bg',  text: 'text-warning' },

  // ── Billing statuses ─────────────────────────────────
  'billed':         { label: 'Cobrado',        dot: 'bg-success',  bg: 'bg-success-bg',  text: 'text-success' },
  'billable':       { label: 'A Cobrar',       dot: 'bg-info',     bg: 'bg-info-bg',     text: 'text-info' },
  'not_billable':   { label: 'Não Faturável',  dot: 'bg-warning',  bg: 'bg-warning-bg',  text: 'text-warning' },
  'waiver_required':{ label: 'Necessita Dispensa', dot: 'bg-error', bg: 'bg-error-bg',   text: 'text-error' },
  'draft':          { label: 'Rascunho',       dot: 'bg-info',     bg: 'bg-info-bg',     text: 'text-info' },
  'issued':         { label: 'Emitida',        dot: 'bg-success',  bg: 'bg-success-bg',  text: 'text-success' },

  // ── Document / compliance statuses ───────────────────
  'valid':          { label: 'Válido',         dot: 'bg-success',  bg: 'bg-success-bg',  text: 'text-success' },
  'expiring_soon':  { label: 'A Vencer',       dot: 'bg-warning',  bg: 'bg-warning-bg',  text: 'text-warning' },
  'expired':        { label: 'Vencido',        dot: 'bg-error',    bg: 'bg-error-bg',    text: 'text-error' },

  // ── Maintenance / work order statuses ────────────────
  'open':           { label: 'Aberta',         dot: 'bg-info',     bg: 'bg-info-bg',     text: 'text-info' },
  'in_progress':    { label: 'Em Curso',       dot: 'bg-amber',    bg: 'bg-amber-light', text: 'text-amber-dark' },
  'completed':      { label: 'Concluída',      dot: 'bg-success',  bg: 'bg-success-bg',  text: 'text-success' },

  // ── Dispatch / clearance statuses ────────────────────
  'pending':        { label: 'Pendente',       dot: 'bg-warning',  bg: 'bg-warning-bg',  text: 'text-warning' },
  'approved':       { label: 'Aprovado',       dot: 'bg-success',  bg: 'bg-success-bg',  text: 'text-success' },
  'blocked':        { label: 'Bloqueado',      dot: 'bg-error',    bg: 'bg-error-bg',    text: 'text-error' },

  // ── Client statuses ───────────────────────────────────
  'activo':         { label: 'Activo',         dot: 'bg-success',  bg: 'bg-success-bg',  text: 'text-success' },
  'inactivo':       { label: 'Inactivo',       dot: 'bg-error',    bg: 'bg-error-bg',    text: 'text-error' },
} as const

export type StatusKey = keyof typeof statusConfig

export function StatusBadge({
  status,
  label: overrideLabel,
  className,
}: {
  status: StatusKey | string
  label?: string
  className?: string
}) {
  const cfg = statusConfig[status as StatusKey] ?? {
    label: status,
    dot: 'bg-muted',
    bg: 'bg-surface-2',
    text: 'text-ink-2',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-sm px-2 py-0.5 text-xs font-semibold whitespace-nowrap',
        cfg.bg,
        cfg.text,
        className
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', cfg.dot)} />
      {overrideLabel ?? cfg.label}
    </span>
  )
}
