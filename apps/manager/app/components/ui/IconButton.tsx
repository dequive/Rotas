'use client'

import { cn } from '@/lib/utils'
import type { ButtonHTMLAttributes } from 'react'

export type IconButtonVariant = 'default' | 'danger'
export type IconButtonSize = 'sm' | 'md'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: IconButtonVariant
  size?: IconButtonSize
  label?: string  // accessible aria-label
}

const variantClasses: Record<IconButtonVariant, string> = {
  default: 'bg-surface text-ink-2 border border-border hover:bg-surface-2 hover:text-ink',
  danger:  'bg-surface text-error border border-error-border hover:bg-error-bg',
}

const sizeClasses: Record<IconButtonSize, string> = {
  sm: 'h-7 w-7',
  md: 'h-8 w-8',
}

export function IconButton({
  variant = 'default',
  size = 'md',
  label,
  className,
  children,
  ...props
}: IconButtonProps) {
  return (
    <button
      {...props}
      aria-label={label}
      className={cn(
        'inline-flex items-center justify-center rounded-md flex-shrink-0',
        'transition-colors duration-100 cursor-pointer',
        'disabled:opacity-60 disabled:cursor-not-allowed',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
    >
      {children}
    </button>
  )
}
