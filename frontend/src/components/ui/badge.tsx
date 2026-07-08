import { cn } from "@/lib/cn";

export function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-black/15 bg-white px-2.5 py-0.5 text-xs font-semibold text-[var(--ar-mist)]",
        className
      )}
    >
      {children}
    </span>
  );
}
