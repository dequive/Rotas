import { cn } from '@/lib/utils'

interface SectionHeaderProps {
  title: string
  count?: number            // Shown as a badge: "12"
  description?: string
  actions?: React.ReactNode
  className?: string
}

export function SectionHeader({
  title,
  count,
  description,
  actions,
  className,
}: SectionHeaderProps) {
  return (
    <div className={cn(
      'flex items-center justify-between gap-3 px-4 py-3 border-b border-border bg-surface-2',
      className
    )}>
      <div className="flex items-center gap-2 min-w-0">
        <h2 className="text-[14px] font-semibold text-ink leading-none">{title}</h2>
        {count !== undefined && (
          <span className="text-[11px] font-semibold text-muted bg-surface border border-border rounded px-1.5 py-0.5 tabular-nums leading-none">
            {count}
          </span>
        )}
        {description && (
          <span className="text-[12px] text-muted hidden md:inline">{description}</span>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>
      )}
    </div>
  )
}
