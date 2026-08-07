import { Reveal } from "@/components/ui/reveal";
import { cn } from "@/lib/cn";

type SectionHeadingProps = {
  eyebrow?: string;
  title: React.ReactNode;
  description?: string;
  align?: "left" | "center";
  tone?: "light" | "dark";
  className?: string;
  titleAs?: "h2" | "h3";
  id?: string;
};

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "left",
  tone = "light",
  className,
  titleAs: TitleTag = "h2",
  id,
}: SectionHeadingProps) {
  const dark = tone === "dark";

  return (
    <div className={cn("max-w-2xl", align === "center" && "mx-auto text-center", className)}>
      {eyebrow ? (
        <Reveal>
          <p
            className={cn(
              "mb-4 inline-flex items-center gap-2 text-[0.78rem] font-semibold uppercase tracking-[0.2em]",
              dark ? "text-[#7fb6ff]" : "text-[var(--ar-sky)]"
            )}
          >
            <span
              className="h-1 w-6 rounded-full bg-[image:var(--ar-accent-gradient)]"
              aria-hidden
            />
            {eyebrow}
          </p>
        </Reveal>
      ) : null}
      <Reveal delay={eyebrow ? 60 : 0}>
        <TitleTag
          id={id}
          className={cn(
            "text-balance text-[2.15rem] font-semibold leading-[1.1] tracking-[-0.035em] sm:text-[2.75rem] lg:text-[3.15rem]",
            dark ? "text-white" : "text-[var(--ar-black)]"
          )}
        >
          {title}
        </TitleTag>
      </Reveal>
      {description ? (
        <Reveal delay={120}>
          <p
            className={cn(
              "mt-5 max-w-xl text-lg leading-relaxed",
              align === "center" && "mx-auto",
              dark ? "text-white/55" : "text-[var(--ar-mist)]"
            )}
          >
            {description}
          </p>
        </Reveal>
      ) : null}
    </div>
  );
}

type LandingSectionProps = {
  id?: string;
  children: React.ReactNode;
  className?: string;
  tone?: "default" | "muted" | "cosmos";
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
        "relative scroll-mt-24 py-20 sm:py-24 lg:py-28",
        tone === "default" && "bg-white",
        tone === "muted" && "daylight",
        tone === "cosmos" && "cosmos cosmos-stars",
        className
      )}
    >
      <div className="relative mx-auto w-full max-w-6xl px-5 sm:px-8">{children}</div>
    </section>
  );
}
