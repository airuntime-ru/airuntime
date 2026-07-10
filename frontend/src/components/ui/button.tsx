"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-[var(--ar-radius-sm)] text-sm font-semibold tracking-[-0.01em] transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/30 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.99]",
  {
    variants: {
      variant: {
        default:
          "border border-white/10 bg-[image:var(--ar-accent-gradient)] text-white shadow-[0_10px_28px_rgba(35,136,255,0.28)] hover:brightness-[1.06] hover:shadow-[0_14px_34px_rgba(35,136,255,0.36)]",
        ghost:
          "text-[var(--ar-graphite)] hover:bg-black/5",
        accent:
          "border border-white/10 bg-[image:var(--ar-accent-gradient)] text-white shadow-[0_10px_28px_rgba(35,136,255,0.28)] hover:brightness-[1.06] hover:shadow-[0_14px_34px_rgba(35,136,255,0.36)]",
        outline:
          "border border-black/12 bg-white text-[var(--ar-graphite)] hover:border-[var(--ar-sky)]/35 hover:bg-[rgba(35,136,255,0.04)]",
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
