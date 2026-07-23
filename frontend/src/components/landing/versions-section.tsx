"use client";

import { useEffect, useState } from "react";
import { Archive, History, RotateCcw } from "lucide-react";
import { useReducedMotion } from "framer-motion";

import { LandingSection, SectionHeading, StatusChip } from "@/components/landing/section";
import { versionActions, versionTimeline } from "@/lib/landing/content";
import { cn } from "@/lib/cn";

const actionIcons = [History, Archive, RotateCcw] as const;

export function VersionsSection() {
  const reduceMotion = useReducedMotion();
  const [active, setActive] = useState(
    versionTimeline.findIndex((item) => item.current) || versionTimeline.length - 1
  );

  useEffect(() => {
    if (reduceMotion) return undefined;
    const timer = window.setInterval(() => {
      setActive((index) => (index + 1) % versionTimeline.length);
    }, 2800);
    return () => window.clearInterval(timer);
  }, [reduceMotion]);

  const current = versionTimeline[active];

  return (
    <LandingSection ariaLabelledBy="versions-title">
      <SectionHeading
        eyebrow="Контроль версий"
        title="Экспериментируйте, не боясь потерять рабочую версию."
        description="Каждый значимый шаг сохраняется. Можно открыть файлы, скачать архив или сделать rollback."
        id="versions-title"
      />

      <div className="mt-10 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <ol className="relative space-y-0 border-l border-black/[0.1] pl-5 sm:pl-6">
          {versionTimeline.map((item, index) => {
            const selected = index === active;
            return (
              <li key={item.version} className="relative pb-6 last:pb-0">
                <span
                  className={cn(
                    "absolute -left-[1.55rem] top-1.5 h-2.5 w-2.5 rounded-full border-2 sm:-left-[1.8rem]",
                    selected
                      ? "border-[var(--ar-sky)] bg-[var(--ar-sky)]"
                      : "border-black/20 bg-white"
                  )}
                  aria-hidden
                />
                <button
                  type="button"
                  onClick={() => setActive(index)}
                  className={cn(
                    "w-full rounded-[0.75rem] border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35",
                    selected
                      ? "border-[var(--ar-sky)]/30 bg-[rgba(35,136,255,0.05)]"
                      : "border-transparent hover:border-black/10 hover:bg-[#f7f8fa]"
                  )}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-[var(--ar-sky)]">{item.version}</span>
                    <span className="text-sm font-semibold text-[var(--ar-black)]">{item.label}</span>
                    {item.current ? <StatusChip tone="sky">current</StatusChip> : null}
                  </div>
                  <p className="mt-1 text-sm text-[var(--ar-mist)]">{item.detail}</p>
                </button>
              </li>
            );
          })}
        </ol>

        <aside className="rounded-[1rem] border border-black/[0.09] bg-[#f7f8fa] p-5 sm:p-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--ar-stone)]">
            Выбрано
          </p>
          <h3 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-[var(--ar-black)]">
            {current.version} · {current.label}
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-[var(--ar-mist)]">{current.detail}</p>

          <ul className="mt-6 space-y-2">
            {versionActions.map((action, index) => {
              const Icon = actionIcons[index];
              return (
                <li
                  key={action}
                  className="flex items-center gap-3 rounded-[0.65rem] border border-black/[0.08] bg-white px-3.5 py-3 text-sm font-medium text-[var(--ar-graphite)]"
                >
                  <Icon size={16} className="text-[var(--ar-sky)]" aria-hidden />
                  {action}
                </li>
              );
            })}
          </ul>
        </aside>
      </div>
    </LandingSection>
  );
}
