import { cn } from '@/lib/utils'
import type { ReactNode, LabelHTMLAttributes } from 'react'

interface FormFieldProps {
  label: string
  htmlFor?: string
  hint?: string
  error?: string
  required?: boolean
  className?: string
  labelProps?: LabelHTMLAttributes<HTMLLabelElement>
  children: ReactNode
}

export function FormField({
  label,
  htmlFor,
  hint,
  error,
  required,
  className,
  labelProps,
  children,
}: FormFieldProps) {
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <label
        htmlFor={htmlFor}
        className="text-[11px] font-semibold uppercase tracking-wide text-muted"
        {...labelProps}
      >
        {label}
        {required && <span className="text-error ml-0.5">*</span>}
      </label>
      {children}
      {hint && !error && (
        <p className="text-[11px] text-muted">{hint}</p>
      )}
      {error && (
        <p className="text-[11px] text-error">{error}</p>
      )}
    </div>
  )
}
