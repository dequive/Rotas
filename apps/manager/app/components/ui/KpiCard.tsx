import { cn } from '@/lib/utils'

interface TrendProps {
  direction: 'up' | 'down' | 'neutral'
  label: string
  positiveIsUp?: boolean  // true = up arrow is green; false = up arrow is red (e.g. cost metrics)
}

interface KpiCardProps {
  label: string
  value: string | number
  trend?: TrendProps
  icon?: React.ReactNode
  semantic?: 'default' | 'primary' | 'accent' | 'amber' | 'error' | 'success' | 'warning' | 'info'
  className?: string
  // For loading state — pass true to show skeleton
  loading?: boolean
}

const semanticValueColor: Record<NonNullable<KpiCardProps['semantic']>, string> = {
  default: 'text-ink',
  primary: 'text-rotas-600',
  accent:  'text-accent-action-600',
  amber:   'text-accent-action-600',
  error:   'text-error',
  success: 'text-success',
  warning: 'text-warning',
  info:    'text-info',
}

export function KpiCard({
  label,
  value,
  trend,
  icon,
  semantic = 'default',
  className,
  loading = false,
}: KpiCardProps) {
  const valueColor = semanticValueColor[semantic]

  if (loading) {
    return (
      <div className={cn(
        'min-h-[104px] rounded-[var(--r-lg)] border border-border bg-surface p-4 shadow-card',
        className
      )}>
        <div className="animate-pulse space-y-3">
          <div className="h-3 w-24 bg-border rounded" />
          <div className="h-7 w-16 bg-border rounded" />
        </div>
      </div>
    )
  }

  return (
    <div className={cn(
      'min-h-[104px] rounded-[var(--r-lg)] border border-border bg-surface p-4 shadow-card',
      className
    )}>
      <div className="flex items-start justify-between mb-3">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted leading-none">
          {label}
        </span>
        {icon && (
          <span className="text-muted flex-shrink-0">{icon}</span>
        )}
      </div>
      <div className={cn(
        'font-mono text-[26px] font-semibold leading-none tabular-nums',
        valueColor
      )}>
        {value}
      </div>
      {trend && (
        <div className={cn(
          'mt-2 text-[11px] flex items-center gap-1',
          trend.direction === 'neutral'
            ? 'text-muted'
            : (trend.direction === 'up') === (trend.positiveIsUp !== false)
              ? 'text-success'
              : 'text-error'
        )}>
          {trend.direction === 'up' ? '↑' : trend.direction === 'down' ? '↓' : '–'}
          <span>{trend.label}</span>
        </div>
      )}
    </div>
  )
}
