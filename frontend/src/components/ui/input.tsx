import { cn } from "@/lib/cn";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-[var(--ar-radius-sm)] border border-[var(--ar-border)] bg-white/80 px-3 text-sm text-[var(--ar-black)] outline-none shadow-sm shadow-sky-950/5 placeholder:text-[var(--ar-stone)] focus:border-[var(--ar-border-strong)] focus:bg-white focus:ring-2 focus:ring-[var(--ar-sky)]/15",
        className
      )}
      {...props}
    />
  );
}
