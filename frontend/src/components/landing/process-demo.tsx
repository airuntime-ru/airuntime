"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, GitCommitHorizontal, Link2, Terminal } from "lucide-react";

import { demoScript } from "@/lib/landing/content";
import { StatusChip } from "@/components/landing/section";
import { cn } from "@/lib/cn";

type Phase =
  | "user"
  | "analyze"
  | "structure"
  | "build"
  | "error"
  | "fix"
  | "deploy"
  | "live";

const PHASE_ORDER: Phase[] = [
  "user",
  "analyze",
  "structure",
  "build",
  "error",
  "fix",
  "deploy",
  "live",
];

const PHASE_MS: Record<Phase, number> = {
  user: 1600,
  analyze: 1400,
  structure: 1400,
  build: 1300,
  error: 1400,
  fix: 1400,
  deploy: 1300,
  live: 2600,
};

function phaseIndex(phase: Phase) {
  return PHASE_ORDER.indexOf(phase);
}

export function ProcessDemo({ className }: { className?: string }) {
  const reduceMotion = useReducedMotion();
  const [animatedPhase, setAnimatedPhase] = useState<Phase>("user");
  const phase: Phase = reduceMotion ? "live" : animatedPhase;

  useEffect(() => {
    if (reduceMotion) return undefined;
    const timer = window.setTimeout(() => {
      setAnimatedPhase((current) => {
        const next = phaseIndex(current) + 1;
        return PHASE_ORDER[next >= PHASE_ORDER.length ? 0 : next];
      });
    }, PHASE_MS[animatedPhase]);
    return () => window.clearTimeout(timer);
  }, [animatedPhase, reduceMotion]);

  const active = phaseIndex(phase);
  const showUser = active >= 0;
  const showAnalyze = active >= 1;
  const showStructure = active >= 2;
  const showBuild = active >= 3;
  const showError = active >= 4 && active < 6;
  const showFixed = active >= 5;
  const showDeploy = active >= 6;
  const showLive = active >= 7;

  const pipeline = useMemo(
    () => [
      { id: "analyze", label: "Анализ", done: showAnalyze },
      { id: "structure", label: "Структура", done: showStructure },
      { id: "build", label: "Build", done: showBuild && showFixed },
      { id: "deploy", label: "Deploy", done: showDeploy },
      { id: "runtime", label: "Runtime", done: showLive },
    ],
    [showAnalyze, showStructure, showBuild, showFixed, showDeploy, showLive]
  );

  return (
    <div
      className={cn(
        "overflow-hidden rounded-[1rem] border border-black/[0.1] bg-white shadow-[0_24px_60px_rgba(7,20,38,0.08)]",
        className
      )}
      aria-label="Демонстрация процесса: от идеи до запуска"
    >
      <div className="flex items-center justify-between gap-3 border-b border-black/[0.07] px-4 py-3 sm:px-5">
        <div>
          <p className="text-sm font-semibold text-[var(--ar-black)]">Проект · Автосервис</p>
          <p className="mt-0.5 text-xs text-[var(--ar-stone)]">Чат → build → deploy → runtime</p>
        </div>
        <StatusChip tone={showLive ? "live" : showError ? "warn" : "sky"}>
          {showLive ? "Запущено" : showError ? "Исправление" : showBuild ? "Сборка" : "В работе"}
        </StatusChip>
      </div>

      <div className="grid lg:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-3 border-b border-black/[0.07] p-4 sm:p-5 lg:border-b-0 lg:border-r">
          {showUser ? (
            <div className="ml-auto max-w-[92%] rounded-[0.85rem] rounded-br-md bg-[var(--ar-black)] px-3.5 py-2.5 text-left text-sm leading-relaxed text-white sm:max-w-[85%]">
              {demoScript.userMessage}
            </div>
          ) : null}

          {showAnalyze ? (
            <div className="max-w-[92%] rounded-[0.85rem] rounded-bl-md bg-[#eef2f7] px-3.5 py-2.5 text-left text-sm leading-relaxed text-[var(--ar-black)] sm:max-w-[88%]">
              {demoScript.analyze}
            </div>
          ) : null}

          {showStructure ? (
            <div className="max-w-[92%] rounded-[0.85rem] rounded-bl-md bg-[#eef2f7] px-3.5 py-2.5 text-left text-sm leading-relaxed text-[var(--ar-black)] sm:max-w-[88%]">
              {demoScript.structure}
            </div>
          ) : null}

          <AnimatePresence initial={false}>
            {showError ? (
              <motion.div
                key="error"
                initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="rounded-[0.75rem] border border-amber-500/25 bg-amber-50 px-3.5 py-2.5 text-left text-sm text-amber-900"
              >
                <p className="font-medium">Build failed</p>
                <p className="mt-0.5 text-amber-800/90">{demoScript.error}</p>
              </motion.div>
            ) : null}
          </AnimatePresence>

          {showFixed && !showError ? (
            <div className="max-w-[92%] rounded-[0.85rem] rounded-bl-md bg-[#eef2f7] px-3.5 py-2.5 text-left text-sm leading-relaxed text-[var(--ar-black)] sm:max-w-[88%]">
              {demoScript.fix}
            </div>
          ) : null}

          {showLive ? (
            <div className="rounded-[0.75rem] border border-emerald-500/20 bg-emerald-50 px-3.5 py-3 text-left">
              <p className="flex items-center gap-2 text-sm font-semibold text-emerald-800">
                <CheckCircle2 size={16} aria-hidden />
                {demoScript.live}
              </p>
              <p className="mt-1 flex items-center gap-1.5 font-mono text-sm text-emerald-700">
                <Link2 size={14} aria-hidden />
                {demoScript.url}
              </p>
            </div>
          ) : null}
        </div>

        <div className="space-y-4 bg-[#f7f8fa] p-4 sm:p-5">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--ar-stone)]">
              Pipeline
            </p>
            <ol className="mt-3 space-y-2">
              {pipeline.map((step) => (
                <li
                  key={step.id}
                  className={cn(
                    "flex items-center justify-between rounded-[0.65rem] border px-3 py-2 text-sm",
                    step.done
                      ? "border-[var(--ar-sky)]/20 bg-white text-[var(--ar-black)]"
                      : "border-transparent bg-transparent text-[var(--ar-stone)]"
                  )}
                >
                  <span>{step.label}</span>
                  <span className="font-mono text-[11px] uppercase tracking-wide">
                    {step.done ? "ok" : "…"}
                  </span>
                </li>
              ))}
            </ol>
          </div>

          <div className="rounded-[0.75rem] border border-black/[0.08] bg-white p-3">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--ar-stone)]">
              <Terminal size={12} aria-hidden />
              Docker build
            </p>
            <p className="mt-2 font-mono text-xs leading-relaxed text-[var(--ar-graphite)]">
              {showLive || (showBuild && showFixed)
                ? "✓ build succeeded"
                : showError
                  ? "✗ dependency missing"
                  : showBuild
                    ? "▸ building image…"
                    : "waiting for sources"}
            </p>
          </div>

          <div className="rounded-[0.75rem] border border-black/[0.08] bg-white p-3">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--ar-stone)]">
              <GitCommitHorizontal size={12} aria-hidden />
              Git
            </p>
            <p className="mt-2 font-mono text-xs text-[var(--ar-graphite)]">
              {showStructure || showLive ? demoScript.commit : "—"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
