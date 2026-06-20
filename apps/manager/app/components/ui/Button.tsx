'use client'

import { cn } from '@/lib/utils'
import type { ButtonHTMLAttributes } from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:   'bg-amber text-ink border border-amber hover:bg-amber-dark hover:border-amber-dark',
  secondary: 'bg-surface text-ink border border-border hover:bg-surface-2',
  ghost:     'bg-transparent text-ink border border-border hover:bg-surface-2',
  danger:    'bg-transparent text-error border border-error hover:bg-error-bg',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-[38px] px-[14px] text-sm gap-2',
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
      className={cn(
        'inline-flex items-center justify-center font-bold rounded-r-md whitespace-nowrap',
        'transition-colors duration-100 cursor-pointer',
        'disabled:opacity-60 disabled:cursor-not-allowed',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
    >
      {loading ? '...' : children}
    </button>
  )
}
