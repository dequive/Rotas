'use client'

import { cn } from '@/lib/utils'
import { LoaderCircle } from 'lucide-react'
import type { ButtonHTMLAttributes } from 'react'

export type ButtonVariant =
  | 'primary'
  | 'secondary'
  | 'accent'
  | 'ghost'
  | 'destructive'
  | 'danger'
  | 'outline'
export type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'border border-rotas-500 bg-rotas-500 text-white shadow-design-sm hover:border-rotas-600 hover:bg-rotas-600',
  secondary:
    'border border-border bg-surface text-ink shadow-design-sm hover:border-border-strong hover:bg-surface-2',
  accent:
    'border border-accent-action-600 bg-accent-action-600 text-white shadow-design-sm hover:border-accent-action-500 hover:bg-accent-action-500',
  ghost:
    'border border-transparent bg-transparent text-ink hover:bg-rotas-50 dark:hover:bg-surface-2',
  destructive:
    'border border-status-cancelled bg-status-cancelled text-white hover:opacity-90',
  danger:
    'border border-status-cancelled bg-status-cancelled text-white hover:opacity-90',
  outline:
    'border border-border bg-transparent text-ink hover:border-border-strong hover:bg-surface-2',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5 [@media(pointer:coarse)]:min-h-11',
  md: 'h-10 px-4 text-sm gap-2 [@media(pointer:coarse)]:min-h-11',
  lg: 'h-12 px-5 text-base gap-2.5',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-[var(--r-md)] font-semibold',
        'transition-colors duration-100 cursor-pointer',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2',
        'disabled:opacity-60 disabled:cursor-not-allowed',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
    >
      {loading ? (
        <>
          <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
          <span>A processar…</span>
        </>
      ) : children}
    </button>
  )
}
