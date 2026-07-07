"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { Card } from "@/components/ui/card";

type ChatStep =
  | { kind: "user"; text: string }
  | { kind: "typing" }
  | { kind: "assistant"; text: string }
  | { kind: "deploy" };

const script: ChatStep[] = [
  { kind: "user", text: "Сделай Telegram-бота с FAQ и передачей оператору." },
  { kind: "typing" },
  { kind: "assistant", text: "План готов. Пишу обработчики, тесты и конфиг деплоя…" },
  { kind: "deploy" },
];

function TypingDots() {
  return (
    <div className="flex items-center gap-1 px-1 py-2">
      {[0, 1, 2].map((index) => (
        <motion.span
          key={index}
          className="h-2 w-2 rounded-full bg-[var(--ar-sky)]"
          animate={{ opacity: [0.25, 1, 0.25], y: [0, -3, 0] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: index * 0.15 }}
        />
      ))}
    </div>
  );
}

export function ProductPreview() {
  const [stepIndex, setStepIndex] = useState(0);
  const [visibleCount, setVisibleCount] = useState(0);

  const current = script[stepIndex];
  const typedText =
    current.kind === "user" || current.kind === "assistant" ? current.text.slice(0, visibleCount) : "";

  useEffect(() => {
    if (current.kind !== "user" && current.kind !== "assistant") {
      return undefined;
    }

    const text = current.text;
    let count = 0;
    const timer = window.setInterval(() => {
      count += 1;
      setVisibleCount(count);
      if (count >= text.length) {
        window.clearInterval(timer);
      }
    }, 28);

    return () => window.clearInterval(timer);
  }, [stepIndex, current]);

  useEffect(() => {
    const delays: Record<ChatStep["kind"], number> = {
      user: 900,
      typing: 1200,
      assistant: 900,
      deploy: 1800,
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
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15, duration: 0.6 }}
    >
      <motion.div
        animate={{ y: [0, -10, 0] }}
        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
      >
        <Card hover={false} className="relative overflow-hidden p-0">
          <div className="border-b border-[var(--ar-border)] px-4 py-3 text-xs text-[var(--ar-stone)]">
            AIRuntime / чат проекта
          </div>
          <div className="min-h-[220px] space-y-3 p-4">
            <AnimatePresence mode="wait">
              {current.kind === "user" ? (
                <motion.div
                  key="user"
                  initial={{ opacity: 0, x: 16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  className="ml-auto max-w-[88%] rounded-[var(--ar-radius-md)] bg-[var(--ar-surface-1)] p-3 text-sm text-[var(--ar-mist)]"
                >
                  {typedText}
                  <motion.span
                    className="ml-0.5 inline-block h-4 w-0.5 bg-[var(--ar-sky)]"
                    animate={{ opacity: [1, 0, 1] }}
                    transition={{ duration: 0.8, repeat: Infinity }}
                  />
                </motion.div>
              ) : null}

              {current.kind === "typing" ? (
                <motion.div
                  key="typing"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="max-w-[70%] rounded-[var(--ar-radius-md)] border border-[var(--ar-border)] bg-[var(--ar-surface-2)] px-3"
                >
                  <TypingDots />
                </motion.div>
              ) : null}

              {current.kind === "assistant" ? (
                <motion.div
                  key="assistant"
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 8 }}
                  className="max-w-[88%] rounded-[var(--ar-radius-md)] border border-[var(--ar-border-strong)] bg-[var(--ar-surface-2)] p-3 text-sm text-[var(--ar-cloud)]"
                >
                  {typedText}
                  <motion.span
                    className="ml-0.5 inline-block h-4 w-0.5 bg-[var(--ar-cyan)]"
                    animate={{ opacity: [1, 0, 1] }}
                    transition={{ duration: 0.8, repeat: Infinity }}
                  />
                </motion.div>
              ) : null}

              {current.kind === "deploy" ? (
                <motion.div
                  key="deploy"
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center justify-between rounded-[var(--ar-radius-md)] border border-[var(--ar-border)] bg-black/20 px-3 py-2 text-xs text-[var(--ar-stone)]"
                >
                  <span>Деплой</span>
                  <motion.span
                    className="rounded-full bg-[var(--ar-cyan)]/15 px-2 py-0.5 font-medium text-[var(--ar-cyan)]"
                    animate={{ boxShadow: ["0 0 0 rgba(78,224,216,0)", "0 0 18px rgba(78,224,216,0.35)", "0 0 0 rgba(78,224,216,0)"] }}
                    transition={{ duration: 1.6, repeat: Infinity }}
                  >
                    live
                  </motion.span>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        </Card>
      </motion.div>
    </motion.div>
  );
}
