import { cn } from "@/lib/cn";

export function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-[var(--ar-border)] bg-[var(--ar-surface-1)] px-2.5 py-0.5 text-xs text-[var(--ar-mist)]",
        className
      )}
    >
      {children}
    </span>
  );
}
