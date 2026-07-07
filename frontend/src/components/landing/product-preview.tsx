"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, Rocket, Sparkles } from "lucide-react";

import { Card } from "@/components/ui/card";

type ChatStep =
  | { kind: "user"; text: string }
  | { kind: "typing" }
  | { kind: "assistant"; text: string }
  | { kind: "deploy" };

const script: ChatStep[] = [
  { kind: "user", text: "Сделай Telegram-бота с FAQ, оплатой и передачей оператору." },
  { kind: "typing" },
  { kind: "assistant", text: "План готов. Собираю сценарии, подключаю хранение заявок и готовлю запуск." },
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
  const reduceMotion = useReducedMotion();
  const [floatEnabled, setFloatEnabled] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [visibleCount, setVisibleCount] = useState(0);

  const current = script[stepIndex];
  const typedText =
    current.kind === "user" || current.kind === "assistant" ? current.text.slice(0, visibleCount) : "";

  useEffect(() => {
    const media = window.matchMedia("(min-width: 640px)");
    const update = () => setFloatEnabled(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (current.kind !== "user" && current.kind !== "assistant") return undefined;
    const text = current.text;
    let count = 0;
    const timer = window.setInterval(() => {
      count += 1;
      setVisibleCount(count);
      if (count >= text.length) window.clearInterval(timer);
    }, 24);
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

  const card = (
    <Card hover={false} className="relative overflow-hidden p-0">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[var(--ar-sky)] via-[var(--ar-cyan)] to-[var(--ar-mint)]" />
      <div className="flex items-center justify-between border-b border-[var(--ar-border)] px-4 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">Live builder</p>
          <p className="mt-1 text-sm text-[var(--ar-mist)]">Проект создается в диалоге</p>
        </div>
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--ar-radius-sm)] bg-sky-50 text-[var(--ar-sky)]">
          <Sparkles size={18} />
        </span>
      </div>
      <div className="min-h-[220px] space-y-3 p-4 sm:min-h-[260px]">
        <AnimatePresence mode="wait">
          {current.kind === "user" ? (
            <motion.div
              key="user"
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              className="ml-auto max-w-[92%] rounded-[var(--ar-radius-sm)] bg-[var(--ar-black)] p-3 text-sm leading-relaxed text-white shadow-lg shadow-slate-950/10 sm:max-w-[86%]"
            >
              {typedText}
              <motion.span
                className="ml-0.5 inline-block h-4 w-0.5 bg-[var(--ar-cyan)]"
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
              className="max-w-[70%] rounded-[var(--ar-radius-sm)] border border-[var(--ar-border)] bg-white px-3 shadow-sm shadow-sky-950/5"
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
              className="max-w-[92%] rounded-[var(--ar-radius-sm)] border border-[var(--ar-border-strong)] bg-white p-3 text-sm leading-relaxed text-[var(--ar-black)] shadow-sm shadow-sky-950/5 sm:max-w-[88%]"
            >
              {typedText}
              <motion.span
                className="ml-0.5 inline-block h-4 w-0.5 bg-[var(--ar-sky)]"
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
              className="space-y-3 rounded-[var(--ar-radius-sm)] border border-[var(--ar-border-strong)] bg-white p-4 shadow-sm shadow-sky-950/5"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--ar-radius-sm)] bg-emerald-50 text-emerald-600">
                  <Rocket size={18} />
                </span>
                <motion.span
                  className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700"
                  animate={{ boxShadow: ["0 0 0 rgba(16,185,129,0)", "0 0 22px rgba(16,185,129,0.28)", "0 0 0 rgba(16,185,129,0)"] }}
                  transition={{ duration: 1.6, repeat: Infinity }}
                >
                  запущено
                </motion.span>
              </div>
              <div>
                <p className="font-semibold text-[var(--ar-black)]">Готовая рабочая ссылка</p>
                <p className="mt-1 text-sm text-[var(--ar-mist)]">airuntime.app/client-faq-bot</p>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
      <div className="grid grid-cols-3 border-t border-[var(--ar-border)] bg-white/50 text-center text-xs text-[var(--ar-mist)]">
        {["План", "Сборка", "Запуск"].map((item) => (
          <div key={item} className="flex items-center justify-center gap-1.5 px-2 py-3">
            <CheckCircle2 size={14} className="text-emerald-500" />
            <span>{item}</span>
          </div>
        ))}
      </div>
    </Card>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15, duration: 0.6 }}
      className="w-full"
    >
      <motion.div
        animate={!reduceMotion && floatEnabled ? { y: [0, -10, 0] } : false}
        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
      >
        {card}
      </motion.div>
    </motion.div>
  );
}
