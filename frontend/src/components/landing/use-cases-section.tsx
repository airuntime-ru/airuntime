"use client";

import { useState } from "react";

import { LandingSection, SectionHeading } from "@/components/landing/section";
import { useCases } from "@/lib/landing/content";
import { trackLandingEvent } from "@/lib/landing/analytics";
import { cn } from "@/lib/cn";

export function UseCasesSection() {
  const [activeId, setActiveId] = useState(useCases[0].id);
  const active = useCases.find((item) => item.id === activeId) ?? useCases[0];

  return (
    <LandingSection tone="muted" ariaLabelledBy="usecases-title">
      <SectionHeading
        eyebrow="Что можно создать"
        title="Конкретные сценарии, а не абстрактные «AI-проекты»."
        description="Стек выбирает агент исходя из задачи — вам не нужно заранее решать, на чём собирать."
        id="usecases-title"
      />

      <div className="mt-10 grid gap-6 lg:grid-cols-[1fr_0.85fr] lg:items-start">
        <ul className="grid gap-2 sm:grid-cols-2">
          {useCases.map((item) => {
            const selected = item.id === activeId;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => {
                    setActiveId(item.id);
                    trackLandingEvent("use_case_selected", { use_case: item.id });
                  }}
                  aria-pressed={selected}
                  className={cn(
                    "flex h-full w-full flex-col rounded-[0.75rem] border px-4 py-3.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35",
                    selected
                      ? "border-[var(--ar-sky)]/35 bg-white shadow-[0_10px_28px_rgba(7,20,38,0.06)]"
                      : "border-black/[0.07] bg-transparent hover:border-black/15 hover:bg-white/70"
                  )}
                >
                  <span className="text-sm font-semibold text-[var(--ar-black)]">{item.title}</span>
                  <span className="mt-1 text-sm text-[var(--ar-mist)]">{item.detail}</span>
                </button>
              </li>
            );
          })}
        </ul>

        <aside className="rounded-[1rem] border border-black/[0.09] bg-white p-5 sm:p-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--ar-sky)]">
            Сценарий
          </p>
          <h3 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-[var(--ar-black)]">
            {active.title}
          </h3>
          <p className="mt-3 text-base leading-relaxed text-[var(--ar-mist)]">{active.detail}</p>
          <div className="mt-6 border-t border-black/[0.07] pt-5">
            <p className="text-sm text-[var(--ar-graphite)]">
              Пример запроса: «Собери {active.title.toLowerCase()} и сразу запусти рабочую версию».
            </p>
          </div>
        </aside>
      </div>
    </LandingSection>
  );
}
