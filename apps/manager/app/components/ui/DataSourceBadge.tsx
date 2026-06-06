import { cn } from '@/lib/utils'
import { Gauge, WifiOff } from 'lucide-react'

interface DataSourceBadgeProps {
  source: 'api' | 'fallback' | 'cache'
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
    icon: Gauge,
    text: 'text-info',
    bg: 'bg-info-bg',
    defaultMessage: 'Dados em cache (< 60s).',
  },
  fallback: {
    icon: WifiOff,
    text: 'text-warning',
    bg: 'bg-warning-bg',
    defaultMessage: 'A mostrar dados de fallback — API indisponível.',
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
