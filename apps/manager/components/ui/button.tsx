import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--r-md)] text-sm font-semibold transition-colors duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rotas-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "border border-rotas-500 bg-rotas-500 text-white shadow-design-sm hover:border-rotas-600 hover:bg-rotas-600",
        primary:
          "border border-rotas-500 bg-rotas-500 text-white shadow-design-sm hover:border-rotas-600 hover:bg-rotas-600",
        accent:
          "border border-accent-action-600 bg-accent-action-600 text-white shadow-design-sm hover:border-accent-action-500 hover:bg-accent-action-500",
        destructive:
          "border border-status-cancelled bg-status-cancelled text-white hover:opacity-90",
        outline:
          "border border-border bg-transparent text-ink hover:border-border-strong hover:bg-surface-2",
        secondary:
          "border border-border bg-surface text-ink shadow-design-sm hover:border-border-strong hover:bg-surface-2",
        ghost: "border border-transparent bg-transparent text-ink hover:bg-rotas-50 dark:hover:bg-surface-2",
        link: "text-rotas-600 underline-offset-4 hover:text-rotas-700 hover:underline",
      },
      size: {
        default: "h-10 px-4 [@media(pointer:coarse)]:min-h-11",
        sm: "h-8 px-3 text-xs [@media(pointer:coarse)]:min-h-11",
        lg: "h-12 px-5 text-base",
        icon: "h-10 w-10 [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:w-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
