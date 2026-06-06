import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

interface WorkQueueItem {
  id: string
  reference: string         // Short ID / plate / code (rendered in font-mono)
  title: string             // Main description
  detail?: string           // Secondary line
  meta?: string             // Timestamp or status label
}

interface WorkQueueProps {
  icon: LucideIcon
  title: string
  tone: 'blue' | 'orange' | 'red' | 'green' | 'cyan' | 'amber'
  items: WorkQueueItem[]
  emptyLabel?: string
  className?: string
}

// Lookup object for tone → Tailwind classes (never dynamic concatenation per Pitfall 3)
const toneConfig = {
  blue:   { iconBg: 'bg-info-bg',       iconText: 'text-info',    border: 'border-l-info' },
  orange: { iconBg: 'bg-warning-bg',    iconText: 'text-warning', border: 'border-l-warning' },
  red:    { iconBg: 'bg-error-bg',      iconText: 'text-error',   border: 'border-l-error' },
  green:  { iconBg: 'bg-success-bg',    iconText: 'text-success', border: 'border-l-success' },
  cyan:   { iconBg: 'bg-info-bg',       iconText: 'text-info',    border: 'border-l-info' },
  amber:  { iconBg: 'bg-amber-light',   iconText: 'text-amber-dark', border: 'border-l-amber' },
} as const

export function WorkQueue({
  icon: Icon,
  title,
  tone,
  items,
  emptyLabel = 'Sem registos.',
  className,
}: WorkQueueProps) {
  const tc = toneConfig[tone]

  return (
    <div className={cn(
      'bg-surface border border-border rounded-lg overflow-hidden',
      className
    )}>
      {/* Header */}
      <div className="flex items-center gap-2.5 px-3 py-2.5 border-b border-border bg-surface-2">
        <span className={cn(
          'flex items-center justify-center h-6 w-6 rounded flex-shrink-0',
          tc.iconBg, tc.iconText
        )}>
          <Icon size={13} />
        </span>
        <span className="text-[13px] font-semibold text-ink">{title}</span>
        <span className="ml-auto text-[11px] font-semibold text-muted tabular-nums">
          {items.length}
        </span>
      </div>

      {/* Items */}
      {items.length === 0 ? (
        <div className="py-8 text-center">
          <p className="text-[12px] text-muted">{emptyLabel}</p>
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {items.map((item) => (
            <li
              key={item.id}
              className={cn(
                'px-3 py-2.5 border-l-[3px] hover:bg-surface-2 transition-colors duration-75',
                tc.border
              )}
            >
              <div className="flex items-center justify-between gap-2 mb-0.5">
                <span className="font-mono text-[11px] text-muted">{item.reference}</span>
                {item.meta && (
                  <span className="text-[11px] text-muted flex-shrink-0">{item.meta}</span>
                )}
              </div>
              <p className="text-[13px] font-medium text-ink leading-snug">{item.title}</p>
              {item.detail && (
                <p className="text-[12px] text-muted mt-0.5 leading-snug">{item.detail}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
