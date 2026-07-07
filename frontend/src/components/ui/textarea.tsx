import { cn } from "@/lib/cn";

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-[108px] w-full rounded-[var(--ar-radius-sm)] border border-[var(--ar-border)] bg-white/80 p-3 text-sm text-[var(--ar-black)] outline-none shadow-sm shadow-sky-950/5 placeholder:text-[var(--ar-stone)] focus:border-[var(--ar-border-strong)] focus:bg-white focus:ring-2 focus:ring-[var(--ar-sky)]/15",
        className
      )}
      {...props}
    />
  );
}
