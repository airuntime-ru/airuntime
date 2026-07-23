"use client";

import { Accordion } from "@/components/ui/accordion";
import { LandingSection, SectionHeading } from "@/components/landing/section";
import { faqs } from "@/lib/landing/content";
import { trackLandingEvent } from "@/lib/landing/analytics";

export function FaqSection() {
  return (
    <LandingSection id="faq" tone="muted" ariaLabelledBy="faq-title">
      <SectionHeading
        eyebrow="FAQ"
        title="Короткие ответы на практические вопросы"
        description="Без маркетинговых обещаний — только то, как платформа работает сейчас."
        id="faq-title"
        align="left"
      />

      <div className="mx-auto mt-10 max-w-3xl">
        <Accordion
          items={faqs}
          onOpenChange={(index) => {
            if (index === null) return;
            trackLandingEvent("faq_opened", {
              question: faqs[index]?.question,
              index,
            });
          }}
        />
      </div>
    </LandingSection>
  );
}
