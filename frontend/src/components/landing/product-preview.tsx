"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

type ChatStep =
  | { kind: "user"; text: string }
  | { kind: "typing" }
  | { kind: "assistant"; text: string }
  | { kind: "deploy" };

const script: ChatStep[] = [
  { kind: "user", text: "Сделай бота с FAQ и заявками." },
  { kind: "typing" },
  { kind: "assistant", text: "Готово. Собираю сценарии и готовлю запуск." },
  { kind: "deploy" },
];

function TypingDots() {
  return (
    <div className="flex items-center gap-1 px-1 py-2">
      {[0, 1, 2].map((index) => (
        <motion.span
          key={index}
          className="h-1.5 w-1.5 rounded-full bg-[var(--ar-stone)]"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: index * 0.15 }}
        />
      ))}
    </div>
  );
}

export function ProductPreview() {
  const reduceMotion = useReducedMotion();
  const [stepIndex, setStepIndex] = useState(0);
  const [visibleCount, setVisibleCount] = useState(0);

  const current = script[stepIndex];
  const typedText =
    current.kind === "user" || current.kind === "assistant" ? current.text.slice(0, visibleCount) : "";

  useEffect(() => {
    if (current.kind !== "user" && current.kind !== "assistant") return undefined;
    const text = current.text;
    let count = 0;
    const timer = window.setInterval(() => {
      count += 1;
      setVisibleCount(count);
      if (count >= text.length) window.clearInterval(timer);
    }, 28);
    return () => window.clearInterval(timer);
  }, [stepIndex, current]);

  useEffect(() => {
    const delays: Record<ChatStep["kind"], number> = {
      user: 900,
      typing: 1000,
      assistant: 900,
      deploy: 1600,
    };
    if ((current.kind === "user" || current.kind === "assistant") && visibleCount < current.text.length) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      setVisibleCount(0);
      setStepIndex((index) => (index + 1) % script.length);
    }, delays[current.kind]);
    return () => window.clearTimeout(timer);
  }, [current, visibleCount]);

  return (
    <div className="overflow-hidden rounded-2xl border border-black/[0.08] bg-white shadow-[0_20px_60px_rgba(0,0,0,0.06)]">
      <div className="border-b border-black/[0.06] px-4 py-3 sm:px-5">
        <p className="text-sm font-medium text-[var(--ar-black)]">Чат проекта</p>
      </div>
      <div className="min-h-[200px] space-y-3 p-4 sm:min-h-[220px] sm:p-5">
        <AnimatePresence mode="wait">
          {current.kind === "user" ? (
            <motion.div
              key="user"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-[var(--ar-black)] px-4 py-2.5 text-left text-sm leading-relaxed text-white"
            >
              {typedText}
              {!reduceMotion ? (
                <motion.span
                  className="ml-0.5 inline-block h-3.5 w-px bg-white/70"
                  animate={{ opacity: [1, 0, 1] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                />
              ) : null}
            </motion.div>
          ) : null}

          {current.kind === "typing" ? (
            <motion.div
              key="typing"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="max-w-[70%] rounded-2xl rounded-bl-md bg-[#f5f5f7] px-4 py-2"
            >
              <TypingDots />
            </motion.div>
          ) : null}

          {current.kind === "assistant" ? (
            <motion.div
              key="assistant"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="max-w-[85%] rounded-2xl rounded-bl-md bg-[#f5f5f7] px-4 py-2.5 text-left text-sm leading-relaxed text-[var(--ar-black)]"
            >
              {typedText}
              {!reduceMotion ? (
                <motion.span
                  className="ml-0.5 inline-block h-3.5 w-px bg-[var(--ar-stone)]"
                  animate={{ opacity: [1, 0, 1] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                />
              ) : null}
            </motion.div>
          ) : null}

          {current.kind === "deploy" ? (
            <motion.div
              key="deploy"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="rounded-xl bg-[#f5f5f7] px-4 py-3 text-left"
            >
              <p className="text-sm font-medium text-[var(--ar-black)]">Запущено</p>
              <p className="mt-0.5 text-sm text-[var(--ar-mist)]">airuntime.app/faq-bot</p>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </div>
  );
}
