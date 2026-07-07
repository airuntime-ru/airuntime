"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/cn";

type AutoTextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export function AutoTextarea({ className, value, onChange, ...props }: AutoTextareaProps) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [value]);

  return (
    <textarea
      ref={ref}
      rows={1}
      value={value}
      onChange={onChange}
      className={cn(
        "w-full resize-none rounded-[var(--ar-radius-lg)] border border-white/15 bg-white/5 px-4 py-3 text-[var(--ar-cloud)] placeholder:text-[var(--ar-stone)] focus:border-[var(--ar-sky)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--ar-sky)]/20",
        className
      )}
      {...props}
    />
  );
}
