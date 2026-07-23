"use client";

import { useEffect, useState } from "react";

import { demoScript } from "@/lib/landing/content";
import { cn } from "@/lib/cn";

type Phase = 0 | 1 | 2 | 3;

const PHASE_MS = [1400, 1100, 1100, 2800] as const;

export function ProcessDemo({ className }: { className?: string }) {
  const [animatedPhase, setAnimatedPhase] = useState<Phase>(0);
  const [reduceMotion, setReduceMotion] = useState(false);
  const phase: Phase = reduceMotion ? 3 : animatedPhase;

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduceMotion(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (reduceMotion) return undefined;
    const timer = window.setTimeout(() => {
      setAnimatedPhase((current) => ((current + 1) % 4) as Phase);
    }, PHASE_MS[animatedPhase]);
    return () => window.clearTimeout(timer);
  }, [animatedPhase, reduceMotion]);

  const visibleSteps = Math.min(phase, 3);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-[1rem] border border-black/[0.08] bg-white shadow-[0_20px_50px_rgba(7,20,38,0.07)]",
        className
      )}
      aria-label="Демонстрация: от описания задачи до запуска"
    >
      <div className="border-b border-black/[0.06] px-4 py-3 sm:px-5">
        <p className="text-sm font-semibold text-[var(--ar-black)]">Чат проекта</p>
      </div>

      <div className="space-y-4 p-4 sm:p-5">
        <div className="ml-auto max-w-[92%] rounded-[0.85rem] rounded-br-md bg-[var(--ar-black)] px-3.5 py-2.5 text-sm leading-relaxed text-white sm:max-w-[85%]">
          {demoScript.userMessage}
        </div>

        <ul className="space-y-2.5" aria-live="polite">
          {demoScript.steps.map((step, index) => {
            const done = visibleSteps > index;
            const active = visibleSteps === index && phase < 3;
            return (
              <li
                key={step}
                className={cn(
                  "flex items-center gap-2.5 text-sm transition-opacity duration-300",
                  done || active ? "opacity-100" : "opacity-35"
                )}
              >
                <span
                  className={cn(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
                    done
                      ? "bg-emerald-500 text-white"
                      : active
                        ? "bg-[var(--ar-sky)] text-white"
                        : "bg-black/[0.06] text-[var(--ar-stone)]"
                  )}
                  aria-hidden
                >
                  {done ? "✓" : index + 1}
                </span>
                <span className={cn(done ? "text-[var(--ar-black)]" : "text-[var(--ar-mist)]")}>
                  {step}
                </span>
              </li>
            );
          })}
        </ul>

        <div
          className={cn(
            "rounded-[0.75rem] border px-3.5 py-3 transition-opacity duration-300",
            phase >= 3
              ? "border-emerald-500/25 bg-emerald-50 opacity-100"
              : "border-transparent bg-transparent opacity-0"
          )}
        >
          <p className="text-sm font-semibold text-emerald-800">Готово</p>
          <p className="mt-1 font-mono text-sm text-emerald-700">
            {demoScript.url} <span aria-hidden>↗</span>
          </p>
        </div>
      </div>
    </div>
  );
}
