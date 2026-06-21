'use client'

import { cn } from '@/lib/utils'
import { forwardRef, type InputHTMLAttributes } from 'react'

export type InputVariant = 'default' | 'mono'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  variant?: InputVariant
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ variant = 'default', className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          'w-full h-10 px-3 bg-surface border border-border rounded-md text-sm text-ink',
          'placeholder:text-placeholder',
          'focus:outline-none focus:ring-2 focus:ring-amber/20 focus:border-amber',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'transition-colors duration-100',
          variant === 'mono' && 'font-mono tabular-nums',
          className,
        )}
        {...props}
      />
    )
  }
)
Input.displayName = 'Input'

export default Input
