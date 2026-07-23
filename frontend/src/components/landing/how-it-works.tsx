import { LandingSection, SectionHeading } from "@/components/landing/section";
import { howCopy, howSteps } from "@/lib/landing/content";

export function HowItWorksSection() {
  return (
    <LandingSection id="how-it-works" ariaLabelledBy="how-title">
      <SectionHeading title={howCopy.title} description={howCopy.subtitle} id="how-title" />

      <ol className="mt-10 grid gap-8 sm:grid-cols-3 sm:gap-6">
        {howSteps.map((step, index) => (
          <li key={step.id} className="max-w-sm">
            <p className="font-mono text-sm text-[var(--ar-sky)]">0{index + 1}</p>
            <h3 className="mt-2 text-xl font-semibold tracking-[-0.02em] text-[var(--ar-black)]">
              {step.title}
            </h3>
            <p className="mt-2 text-base leading-relaxed text-[var(--ar-mist)]">{step.detail}</p>
          </li>
        ))}
      </ol>
    </LandingSection>
  );
}
