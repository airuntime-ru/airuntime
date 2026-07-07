import { cn } from "@/lib/cn";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-[var(--ar-radius-md)] border border-[var(--ar-border)] bg-[var(--ar-surface-1)] px-3 text-sm text-[var(--ar-cloud)] outline-none placeholder:text-[var(--ar-stone)] focus:border-[var(--ar-border-strong)] focus:ring-2 focus:ring-[var(--ar-sky)]/20",
        className
      )}
      {...props}
    />
  );
}
