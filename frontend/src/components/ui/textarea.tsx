import { cn } from "@/lib/cn";

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-[90px] w-full rounded-[var(--ar-radius-md)] border border-[var(--ar-border)] bg-[var(--ar-surface-1)] p-3 text-sm text-[var(--ar-cloud)] outline-none placeholder:text-[var(--ar-stone)] focus:border-[var(--ar-border-strong)] focus:ring-2 focus:ring-[var(--ar-sky)]/20",
        className
      )}
      {...props}
    />
  );
}
