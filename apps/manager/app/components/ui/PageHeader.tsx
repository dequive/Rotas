import { cn } from '@/lib/utils'

interface PageHeaderProps {
  eyebrow?: string          // Small uppercase label above title (e.g., "Torre de Controlo")
  title: string             // H1 — Inter 600 24px
  description?: string      // Subtitle text
  actions?: React.ReactNode // Buttons/controls aligned right
  meta?: React.ReactNode    // Metadata below title (e.g., operational date)
  className?: string
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn('mb-6 flex flex-col items-start justify-between gap-4 border-b border-border pb-5 sm:flex-row', className)}>
      <div className="min-w-0">
        {eyebrow && (
          <span className="block text-[11px] font-semibold uppercase tracking-widest text-muted mb-1">
            {eyebrow}
          </span>
        )}
        <h1 className="text-2xl font-semibold leading-tight text-ink">{title}</h1>
        {description && (
          <p className="mt-1 text-[13px] text-muted leading-relaxed">{description}</p>
        )}
        {meta && <div className="mt-2">{meta}</div>}
      </div>
      {actions && (
        <div className="flex w-full flex-wrap items-center gap-2 pt-1 sm:w-auto sm:flex-shrink-0">
          {actions}
        </div>
      )}
    </div>
  )
}
