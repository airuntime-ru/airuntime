import { cn } from "@/lib/cn";

export function Loader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-[var(--ar-mist)]" role="status" aria-live="polite">
      <span className="breathe inline-block h-2 w-2 rounded-full bg-[var(--ar-sky)]" />
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
    <div className={cn("glass rounded-[var(--ar-radius-xl)] p-8 text-center", className)}>
      <h3 className="text-lg font-medium text-[var(--ar-cloud)]">{title}</h3>
      <p className="mt-2 text-sm text-[var(--ar-mist)]">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
