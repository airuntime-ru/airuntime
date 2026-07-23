import { LandingSection, SectionHeading } from "@/components/landing/section";
import { FaqAccordion } from "@/components/landing/faq-accordion";

export function FaqSection() {
  return (
    <LandingSection id="faq" tone="muted" ariaLabelledBy="faq-title">
      <SectionHeading title="Частые вопросы" id="faq-title" />
      <div className="mx-auto mt-10 max-w-3xl">
        <FaqAccordion />
      </div>
    </LandingSection>
  );
}
