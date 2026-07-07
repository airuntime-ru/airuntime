import { cn } from "@/lib/cn";

export function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-[var(--ar-border)] bg-white/80 px-2.5 py-0.5 text-xs font-medium text-[var(--ar-mist)] shadow-sm shadow-sky-950/5",
        className
      )}
    >
      {children}
    </span>
  );
}
