import { LandingSection, SectionHeading } from "@/components/landing/section";
import { trustCopy, trustPoints } from "@/lib/landing/content";

export function TrustSection() {
  return (
    <LandingSection id="trust" ariaLabelledBy="trust-title">
      <SectionHeading title={trustCopy.title} description={trustCopy.subtitle} id="trust-title" />

      <ul className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {trustPoints.map((point) => (
          <li key={point.title} className="max-w-sm">
            <h3 className="text-base font-semibold text-[var(--ar-black)]">{point.title}</h3>
            <p className="mt-1.5 text-[15px] leading-relaxed text-[var(--ar-mist)]">{point.detail}</p>
          </li>
        ))}
      </ul>

      <p className="mt-12 max-w-2xl text-[15px] leading-relaxed text-[var(--ar-stone)]">
        {trustCopy.audienceLine}
      </p>
    </LandingSection>
  );
}
