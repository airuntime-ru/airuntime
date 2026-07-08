import { cn } from "@/lib/cn";

export function Card({
  className,
  hover = true,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-[var(--ar-radius-sm)] border border-black/10 bg-white p-5 shadow-[0_10px_28px_rgba(7,20,38,0.06)]",
        hover && "transition-transform hover:-translate-y-0.5",
        className
      )}
      {...props}
    />
  );
}
