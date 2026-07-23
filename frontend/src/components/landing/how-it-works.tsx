"use client";

import { useEffect, useState } from "react";
import { useReducedMotion } from "framer-motion";

import { LandingSection, SectionHeading, StatusChip } from "@/components/landing/section";
import { howSteps } from "@/lib/landing/content";
import { cn } from "@/lib/cn";

export function HowItWorksSection() {
  const reduceMotion = useReducedMotion();
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (reduceMotion) return undefined;
    const timer = window.setInterval(() => {
      setActive((index) => (index + 1) % howSteps.length);
    }, 3400);
    return () => window.clearInterval(timer);
  }, [reduceMotion]);

  return (
    <LandingSection id="how-it-works" ariaLabelledBy="how-title">
      <SectionHeading
        eyebrow="Как это работает"
        title="Один чат. Три состояния проекта."
        description="Не три одинаковые карточки — последовательный переход Idea → Build → Runtime."
        id="how-title"
      />

      <div className="mt-10 grid gap-3 lg:grid-cols-[0.9fr_1.1fr]">
        <ol className="space-y-2">
          {howSteps.map((step, index) => {
            const isActive = active === index;
            return (
              <li key={step.id}>
                <button
                  type="button"
                  onClick={() => setActive(index)}
                  aria-current={isActive ? "step" : undefined}
                  className={cn(
                    "w-full rounded-[0.85rem] border px-4 py-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35 sm:px-5",
                    isActive
                      ? "border-[var(--ar-black)] bg-[var(--ar-black)] text-white"
                      : "border-black/[0.08] bg-white text-[var(--ar-black)] hover:border-black/20"
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-lg font-semibold tracking-[-0.02em] sm:text-xl">
                      <span className={cn(isActive ? "text-white/45" : "text-[var(--ar-stone)]")}>
                        0{index + 1}
                      </span>{" "}
                      {step.title}
                    </p>
                    <StatusChip tone={isActive ? "sky" : "neutral"}>{step.status}</StatusChip>
                  </div>
                  <p
                    className={cn(
                      "mt-2 text-sm leading-relaxed",
                      isActive ? "text-white/75" : "text-[var(--ar-mist)]"
                    )}
                  >
                    {step.detail}
                  </p>
                </button>
              </li>
            );
          })}
        </ol>

        <div className="relative overflow-hidden rounded-[1rem] border border-black/[0.09] bg-[#f3f5f8] p-5 sm:p-7">
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[var(--ar-sky)]/40 to-transparent"
            aria-hidden
          />
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--ar-stone)]">
            Состояние
          </p>
          <p className="mt-4 text-4xl font-semibold tracking-[-0.04em] text-[var(--ar-black)] sm:text-5xl">
            {howSteps[active].title}
          </p>
          <p className="mt-4 max-w-md text-base leading-relaxed text-[var(--ar-mist)]">
            {howSteps[active].detail}
          </p>

          <div className="mt-8 flex flex-wrap gap-2" aria-hidden>
            {howSteps.map((step, index) => (
              <span
                key={step.id}
                className={cn(
                  "h-1.5 rounded-full transition-all duration-500",
                  index === active ? "w-10 bg-[var(--ar-black)]" : "w-3 bg-black/15"
                )}
              />
            ))}
          </div>

          <div className="mt-8 grid gap-2 font-mono text-xs text-[var(--ar-graphite)]">
            {active === 0 ? (
              <>
                <p>user → «Сделай сайт для записи…»</p>
                <p className="text-[var(--ar-stone)]">agent → уточняет цель и объём</p>
              </>
            ) : null}
            {active === 1 ? (
              <>
                <p>write files · request_secret · request_service</p>
                <p>docker build · read logs · fix</p>
              </>
            ) : null}
            {active === 2 ? (
              <>
                <p>container up · https ready</p>
                <p>public url / telegram bot online</p>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </LandingSection>
  );
}
