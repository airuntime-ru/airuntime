import { cn } from "@/lib/cn";

type SectionHeadingProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  align?: "left" | "center";
  className?: string;
  titleAs?: "h2" | "h3";
  id?: string;
};

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "left",
  className,
  titleAs: TitleTag = "h2",
  id,
}: SectionHeadingProps) {
  return (
    <div
      className={cn(
        "max-w-3xl",
        align === "center" && "mx-auto text-center",
        className
      )}
    >
      {eyebrow ? (
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--ar-sky)]">
          {eyebrow}
        </p>
      ) : null}
      <TitleTag
        id={id}
        className={cn(
          "text-balance text-3xl font-semibold tracking-[-0.03em] text-[var(--ar-black)] sm:text-4xl lg:text-[2.75rem] lg:leading-[1.08]",
          eyebrow && "mt-3"
        )}
      >
        {title}
      </TitleTag>
      {description ? (
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--ar-mist)] sm:text-lg">
          {description}
        </p>
      ) : null}
    </div>
  );
}

type LandingSectionProps = {
  id?: string;
  children: React.ReactNode;
  className?: string;
  tone?: "default" | "muted" | "ink";
  ariaLabelledBy?: string;
};

export function LandingSection({
  id,
  children,
  className,
  tone = "default",
  ariaLabelledBy,
}: LandingSectionProps) {
  return (
    <section
      id={id}
      aria-labelledby={ariaLabelledBy}
      className={cn(
        "relative scroll-mt-24 border-t border-black/[0.06] py-16 sm:py-20 lg:py-24",
        tone === "muted" && "bg-[#f3f5f8]",
        tone === "ink" && "border-transparent bg-[var(--ar-black)] text-white",
        className
      )}
    >
      <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">{children}</div>
    </section>
  );
}

export function StatusChip({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "sky" | "mint" | "warn" | "live";
}) {
  const tones = {
    neutral: "border-black/10 bg-white text-[var(--ar-graphite)]",
    sky: "border-[var(--ar-sky)]/25 bg-[rgba(35,136,255,0.08)] text-[var(--ar-sky)]",
    mint: "border-emerald-500/20 bg-emerald-50 text-emerald-700",
    warn: "border-amber-500/25 bg-amber-50 text-amber-800",
    live: "border-emerald-500/30 bg-emerald-500 text-white",
  } as const;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[0.5rem] border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.08em]",
        tones[tone]
      )}
    >
      {children}
    </span>
  );
}
