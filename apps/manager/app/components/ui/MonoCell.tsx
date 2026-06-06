import { cn } from '@/lib/utils'

interface MonoCellProps {
  children: React.ReactNode
  size?: 'xs' | 'sm' | 'base'
  className?: string
}

const sizeMap = {
  xs:   'text-[11px]',
  sm:   'text-[12px]',
  base: 'text-[13px]',
}

export function MonoCell({ children, size = 'sm', className }: MonoCellProps) {
  return (
    <span className={cn(
      'font-mono tabular-nums',
      sizeMap[size],
      className
    )}>
      {children}
    </span>
  )
}

// Convenience: MoneyCell for monetary values (MZN amounts)
// Shows text-success for positive revenue context, default text-ink for costs
export function MoneyCell({
  value,
  currency = 'MZN',
  semantic = 'default',
  className,
}: {
  value: number | string
  currency?: string
  semantic?: 'default' | 'revenue' | 'cost' | 'error'
  className?: string
}) {
  const colorMap = {
    default: 'text-ink',
    revenue: 'text-success',
    cost:    'text-ink-2',
    error:   'text-error',
  }
  return (
    <span className={cn(
      'font-mono text-[12px] tabular-nums',
      colorMap[semantic],
      className
    )}>
      {currency}{' '}
      {typeof value === 'number'
        ? value.toLocaleString('pt-MZ', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        : value}
    </span>
  )
}
