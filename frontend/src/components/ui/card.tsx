import { cn } from "@/lib/cn";

export function Card({
  className,
  hover = true,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-[var(--ar-radius-md)] border border-black/[0.07] bg-white p-5 shadow-[0_10px_32px_rgba(7,20,38,0.055)] transition-all duration-300",
        hover &&
          "hover:-translate-y-0.5 hover:border-[var(--ar-sky)]/25 hover:shadow-[0_20px_48px_rgba(35,136,255,0.12)]",
        className
      )}
      {...props}
    />
  );
}
