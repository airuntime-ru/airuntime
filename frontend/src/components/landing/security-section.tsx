import { LandingSection, SectionHeading } from "@/components/landing/section";
import { securityPoints } from "@/lib/landing/content";

export function SecuritySection() {
  return (
    <LandingSection id="security" tone="muted" ariaLabelledBy="security-title">
      <SectionHeading
        eyebrow="Безопасность"
        title="Секреты и изоляция — часть продукта, а не послесловие."
        description="Спокойная инженерия: токены не попадают в модель, Docker-операции отделены, запросы проходят модерацию."
        id="security-title"
      />

      <ul className="mt-10 grid gap-px overflow-hidden rounded-[1rem] border border-black/[0.09] bg-black/[0.06] sm:grid-cols-2 lg:grid-cols-3">
        {securityPoints.map((point) => (
          <li key={point.title} className="bg-white p-5 sm:p-6">
            <h3 className="text-base font-semibold tracking-[-0.02em] text-[var(--ar-black)]">
              {point.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--ar-mist)]">{point.detail}</p>
          </li>
        ))}
      </ul>
    </LandingSection>
  );
}
