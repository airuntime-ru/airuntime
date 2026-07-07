import { cn } from "@/lib/cn";

export function Card({
  className,
  hover = true,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean }) {
  return <div className={cn("glass rounded-[var(--ar-radius-sm)] p-5", hover && "glass-hover", className)} {...props} />;
}
