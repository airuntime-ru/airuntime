import { cn } from "@/lib/cn";

type SectionHeadingProps = {
  title: string;
  description?: string;
  align?: "left" | "center";
  className?: string;
  titleAs?: "h2" | "h3";
  id?: string;
};

export function SectionHeading({
  title,
  description,
  align = "left",
  className,
  titleAs: TitleTag = "h2",
  id,
}: SectionHeadingProps) {
  return (
    <div className={cn("max-w-2xl", align === "center" && "mx-auto text-center", className)}>
      <TitleTag
        id={id}
        className="text-balance text-[2rem] font-semibold leading-[1.15] tracking-[-0.03em] text-[var(--ar-black)] sm:text-[2.5rem] lg:text-[2.75rem]"
      >
        {title}
      </TitleTag>
      {description ? (
        <p className="mt-4 max-w-xl text-lg leading-relaxed text-[var(--ar-mist)]">{description}</p>
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
        "relative scroll-mt-24 py-16 sm:py-20 lg:py-24",
        tone === "muted" && "bg-[#f3f5f8]",
        tone === "ink" && "bg-[var(--ar-black)] text-white",
        className
      )}
    >
      <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">{children}</div>
    </section>
  );
}
