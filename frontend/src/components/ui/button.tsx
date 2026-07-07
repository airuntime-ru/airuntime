"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-[var(--ar-radius-sm)] text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/30 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.99] hover:-translate-y-0.5",
  {
    variants: {
      variant: {
        default: "bg-[var(--ar-black)] text-white shadow-sm shadow-slate-950/10 hover:bg-slate-800",
        ghost: "text-[var(--ar-graphite)] hover:bg-white/75 hover:text-[var(--ar-sky)]",
        accent:
          "bg-gradient-to-r from-[var(--ar-sky)] via-[var(--ar-cyan)] to-[var(--ar-mint)] text-white shadow-lg shadow-sky-500/20 hover:shadow-xl hover:shadow-cyan-500/20",
        outline: "border border-[var(--ar-border)] bg-white/55 text-[var(--ar-graphite)] hover:border-[var(--ar-border-strong)] hover:bg-white",
      },
      size: {
        default: "h-10 px-4 py-2",
        lg: "h-12 px-6 text-base",
        sm: "h-8 px-3 text-xs",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
