import { cn } from "@/lib/cn";

export function Loader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-[var(--ar-mist)]" role="status" aria-live="polite">
      <span className="breathe inline-block h-2 w-2 rounded-full bg-[var(--ar-cyan)] shadow-[0_0_18px_rgba(24,199,202,0.35)]" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function PageLoader() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Loader />
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("glass rounded-[var(--ar-radius-sm)] p-8 text-center", className)}>
      <h3 className="text-lg font-semibold text-[var(--ar-black)]">{title}</h3>
      <p className="mt-2 text-sm text-[var(--ar-mist)]">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
