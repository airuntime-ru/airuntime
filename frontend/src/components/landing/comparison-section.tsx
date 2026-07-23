import { LandingSection, SectionHeading } from "@/components/landing/section";
import { comparisonRows } from "@/lib/landing/content";

export function ComparisonSection() {
  return (
    <LandingSection ariaLabelledBy="comparison-title">
      <SectionHeading
        eyebrow="Отличие"
        title="Почему это не обычный AI-генератор"
        description="Генератор интерфейсов отдаёт макет или код. AIRuntime доводит проект до работающей версии."
        id="comparison-title"
      />

      <div className="mt-10 overflow-hidden rounded-[1rem] border border-black/[0.09] bg-white">
        <div className="hidden grid-cols-[1fr_1fr] border-b border-black/[0.07] bg-[#f7f8fa] md:grid">
          <p className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ar-stone)]">
            Обычный генератор
          </p>
          <p className="border-l border-black/[0.07] px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ar-sky)]">
            AIRuntime
          </p>
        </div>

        <ul className="divide-y divide-black/[0.07]">
          {comparisonRows.map((row) => (
            <li key={row.generator} className="grid md:grid-cols-2">
              <div className="px-5 py-4">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--ar-stone)] md:hidden">
                  Обычный генератор
                </p>
                <p className="text-sm leading-relaxed text-[var(--ar-mist)] md:text-[0.95rem]">
                  {row.generator}
                </p>
              </div>
              <div className="border-t border-black/[0.05] bg-[rgba(35,136,255,0.03)] px-5 py-4 md:border-l md:border-t-0 md:border-black/[0.07]">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--ar-sky)] md:hidden">
                  AIRuntime
                </p>
                <p className="text-sm font-medium leading-relaxed text-[var(--ar-black)] md:text-[0.95rem]">
                  {row.airuntime}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </LandingSection>
  );
}
