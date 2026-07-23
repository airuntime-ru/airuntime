import { LandingSection, SectionHeading } from "@/components/landing/section";
import { audienceItems } from "@/lib/landing/content";

export function AudienceSection() {
  return (
    <LandingSection ariaLabelledBy="audience-title">
      <SectionHeading
        eyebrow="Для кого"
        title="Для тех, кому нужен результат, а не ещё один редактор кода."
        description="Задачи, результаты и артефакты — без стоковых портретов."
        id="audience-title"
      />

      <div className="mt-10 grid gap-4 lg:grid-cols-3">
        {audienceItems.map((item, index) => (
          <article
            key={item.id}
            className="flex flex-col border-t-2 border-[var(--ar-black)] bg-[#f7f8fa] px-5 py-6 sm:px-6"
          >
            <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--ar-stone)]">
              0{index + 1}
            </p>
            <h3 className="mt-3 text-xl font-semibold tracking-[-0.03em] text-[var(--ar-black)]">
              {item.title}
            </h3>
            <dl className="mt-5 space-y-4 text-sm">
              <div>
                <dt className="font-medium text-[var(--ar-stone)]">Задача</dt>
                <dd className="mt-1 text-[var(--ar-graphite)]">{item.task}</dd>
              </div>
              <div>
                <dt className="font-medium text-[var(--ar-stone)]">Результат</dt>
                <dd className="mt-1 text-[var(--ar-graphite)]">{item.outcome}</dd>
              </div>
              <div>
                <dt className="font-medium text-[var(--ar-stone)]">Артефакт</dt>
                <dd className="mt-1 font-mono text-xs text-[var(--ar-sky)]">{item.artifact}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </LandingSection>
  );
}
