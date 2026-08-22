import { cn } from '@/lib/utils'
import { AlertTriangle, Database, Gauge, WifiOff } from 'lucide-react'

interface DataSourceBadgeProps {
  source: 'api' | 'cache' | 'degraded' | 'unavailable'
  message?: string
  className?: string
}

const sourceConfig = {
  api: {
    icon: Gauge,
    text: 'text-success',
    bg: 'bg-success-bg',
    defaultMessage: 'Dados em tempo real.',
  },
  cache: {
    icon: Database,
    text: 'text-info',
    bg: 'bg-info-bg',
    defaultMessage: 'Dados em cache (< 60s).',
  },
  degraded: {
    icon: AlertTriangle,
    text: 'text-warning',
    bg: 'bg-warning-bg',
    defaultMessage: 'Dados operacionais degradados.',
  },
  unavailable: {
    icon: WifiOff,
    text: 'text-error',
    bg: 'bg-error-bg',
    defaultMessage: 'Fonte de dados indisponível.',
  },
}

export function DataSourceBadge({
  source,
  message,
  className,
}: DataSourceBadgeProps) {
  const cfg = sourceConfig[source]
  const Icon = cfg.icon

  return (
    <div
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[12px] mb-4',
        cfg.bg,
        cfg.text,
        className
      )}
    >
      <Icon size={13} className="flex-shrink-0" />
      <span>{message ?? cfg.defaultMessage}</span>
    </div>
  )
}
