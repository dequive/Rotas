import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

interface EmptyStateProps {
  title: string
  description?: string
  icon?: LucideIcon
  action?: React.ReactNode
  className?: string
}

export function EmptyState({
  title,
  description,
  icon: Icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div className={cn(
      'py-16 text-center border-t border-border',
      className
    )}>
      {Icon && (
        <div className="flex justify-center mb-3">
          <span className="flex items-center justify-center h-10 w-10 rounded-full bg-surface-2 text-muted">
            <Icon size={20} />
          </span>
        </div>
      )}
      <p className="text-[14px] font-semibold text-ink mb-1">{title}</p>
      {description && (
        <p className="text-[13px] text-muted max-w-xs mx-auto leading-relaxed">{description}</p>
      )}
      {action && (
        <div className="mt-4">{action}</div>
      )}
    </div>
  )
}

// Compact inline empty state (for use inside table cells or small containers)
export function EmptyStateInline({ label = 'Sem registos' }: { label?: string }) {
  return (
    <div className="py-8 text-center">
      <p className="text-[12px] text-muted">{label}</p>
    </div>
  )
}
