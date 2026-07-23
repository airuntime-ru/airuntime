import { LandingSection, SectionHeading } from "@/components/landing/section";
import { useCases, useCasesCopy } from "@/lib/landing/content";

export function UseCasesSection() {
  return (
    <LandingSection id="use-cases" ariaLabelledBy="use-cases-title" tone="muted">
      <SectionHeading
        title={useCasesCopy.title}
        description={useCasesCopy.subtitle}
        id="use-cases-title"
      />

      <ul className="mt-10 grid gap-x-8 gap-y-8 sm:grid-cols-2">
        {useCases.map((item) => (
          <li key={item.id} className="max-w-md">
            <h3 className="text-lg font-semibold tracking-[-0.02em] text-[var(--ar-black)]">
              {item.title}
            </h3>
            <p className="mt-1.5 text-base leading-relaxed text-[var(--ar-mist)]">{item.detail}</p>
            <p className="mt-3 text-sm text-[var(--ar-graphite)]">{item.prompt}</p>
          </li>
        ))}
      </ul>
    </LandingSection>
  );
}
