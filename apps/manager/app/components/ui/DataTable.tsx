import { cn } from '@/lib/utils'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { EmptyStateInline } from '@/app/components/ui/EmptyState'

// Re-export shadcn primitives with ROTAS overrides applied

export function RotasTableHeader({
  className,
  children,
  ...props
}: React.ComponentProps<typeof TableHead>) {
  return (
    <TableHead
      className={cn(
        'text-[11px] font-semibold uppercase tracking-wide text-muted h-9 px-3',
        className
      )}
      {...props}
    >
      {children}
    </TableHead>
  )
}

export function RotasTableRow({
  className,
  ...props
}: React.ComponentProps<typeof TableRow>) {
  return (
    <TableRow
      className={cn(
        'hover:bg-surface-2 transition-colors duration-75 border-b border-border last:border-0',
        className
      )}
      {...props}
    />
  )
}

export function RotasTableCell({
  className,
  ...props
}: React.ComponentProps<typeof TableCell>) {
  return (
    <TableCell
      className={cn('px-3 py-2.5 text-[13px] text-ink', className)}
      {...props}
    />
  )
}

// Sticky actions cell (last column — always pinned right)
export function RotasTableActionsCell({
  className,
  children,
  ...props
}: React.ComponentProps<typeof TableCell>) {
  return (
    <TableCell
      className={cn(
        'px-3 py-2 sticky right-0 bg-surface shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.06)]',
        className
      )}
      {...props}
    >
      <div className="flex items-center gap-1 justify-end">{children}</div>
    </TableCell>
  )
}

// Sticky actions header (paired with RotasTableActionsCell)
export function RotasTableActionsHeader({
  className,
  ...props
}: React.ComponentProps<typeof TableHead>) {
  return (
    <TableHead
      className={cn(
        'sticky right-0 bg-surface-2 shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.06)] w-[80px]',
        className
      )}
      {...props}
    />
  )
}

interface DataTableProps {
  children: React.ReactNode // TableHeader + TableBody rows
  isEmpty?: boolean
  emptyLabel?: string
  className?: string
}

// Full table wrapper with overflow handling
export function DataTable({
  children,
  isEmpty,
  emptyLabel,
  className,
}: DataTableProps) {
  return (
    <div
      className={cn(
        'overflow-x-auto rounded-lg border border-border bg-surface',
        className
      )}
    >
      <Table>{children}</Table>
      {isEmpty && <EmptyStateInline label={emptyLabel} />}
    </div>
  )
}

// Named re-exports of shadcn primitives for convenience (callers import from one place)
export {
  Table,
  TableBody,
  TableHeader,
  TableRow,
  TableCell,
  TableHead,
} from '@/components/ui/table'
