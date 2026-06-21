'use client'

import { useEffect, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { IconButton } from './IconButton'

interface ModalDialogProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  /** Pass 'modal-wide' to use the wide CSS variant */
  className?: string
}

export function ModalDialog({
  open,
  onClose,
  title,
  children,
  className,
}: ModalDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  useEffect(() => {
    if (!open) return
    const timer = setTimeout(() => {
      const focusable = dialogRef.current?.querySelector<HTMLElement>(
        'input, select, textarea, button, [tabindex]:not([tabindex="-1"])'
      )
      focusable?.focus()
    }, 50)
    return () => clearTimeout(timer)
  }, [open])

  if (!open) return null

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-dialog-title"
        className={cn('modal', className)}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="modal-dialog-title">{title}</h2>
          <IconButton onClick={onClose} label="Fechar diálogo">
            <X size={18} />
          </IconButton>
        </div>
        {children}
      </div>
    </div>
  )
}
