import { cn } from "@/lib/cn";

export function Card({
  className,
  hover = true,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-[var(--ar-radius-md)] border border-black/[0.08] bg-white p-5 shadow-[var(--ar-shadow-sm)]",
        hover && "transition-colors hover:border-black/15",
        className
      )}
      {...props}
    />
  );
}
