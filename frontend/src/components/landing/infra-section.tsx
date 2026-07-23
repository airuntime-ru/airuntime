import { LandingSection, SectionHeading } from "@/components/landing/section";
import { infraPoints } from "@/lib/landing/content";

export function InfraSection() {
  return (
    <LandingSection tone="muted" ariaLabelledBy="infra-title">
      <div className="grid gap-10 lg:grid-cols-[0.95fr_1.05fr] lg:items-start">
        <SectionHeading
          eyebrow="Инфраструктура"
          title="Инфраструктура без ручной настройки"
          description="Сначала ценность: проект запускается сам. Затем — как это устроено технически, без DevOps-ритуалов."
          id="infra-title"
        />

        <div className="space-y-0 border-t border-black/[0.08]">
          {infraPoints.map((point, index) => (
            <div
              key={point.title}
              className="grid gap-2 border-b border-black/[0.08] py-5 sm:grid-cols-[7rem_1fr] sm:gap-6"
            >
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--ar-sky)]">
                0{index + 1}
              </p>
              <div>
                <h3 className="text-lg font-semibold tracking-[-0.02em] text-[var(--ar-black)]">
                  {point.title}
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-[var(--ar-mist)] sm:text-[0.95rem]">
                  {point.detail}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-10 overflow-hidden rounded-[1rem] border border-black/[0.09] bg-white">
        <div className="border-b border-black/[0.07] px-5 py-3">
          <p className="text-sm font-semibold text-[var(--ar-black)]">Подключаемые сервисы</p>
        </div>
        <div className="flex flex-wrap gap-2 px-5 py-4">
          {["Postgres", "Redis", "MySQL", "MongoDB", "RabbitMQ"].map((name) => (
            <span
              key={name}
              className="rounded-[0.5rem] border border-black/[0.08] bg-[#f7f8fa] px-3 py-1.5 font-mono text-xs text-[var(--ar-graphite)]"
            >
              {name}
            </span>
          ))}
          <span className="rounded-[0.5rem] border border-dashed border-black/15 px-3 py-1.5 text-xs text-[var(--ar-stone)]">
            и другие по задаче
          </span>
        </div>
      </div>
    </LandingSection>
  );
}
