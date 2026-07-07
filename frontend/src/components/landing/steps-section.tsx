"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

const steps = [
  { title: "Опишите", hint: "Идея — обычным сообщением." },
  { title: "Соберём", hint: "Код, окружение, проверка." },
  { title: "Запустим", hint: "Готовая ссылка на проект." },
];

const STEP_MS = 3200;

function WindStreak({ delay = 0 }: { delay?: number }) {
  return (
    <motion.span
      className="pointer-events-none absolute top-1/2 h-px w-[42vw] max-w-xl bg-gradient-to-r from-transparent via-black/10 to-transparent"
      initial={{ x: "120vw", opacity: 0 }}
      animate={{ x: "-120vw", opacity: [0, 0.55, 0] }}
      transition={{ duration: 1.1, delay, ease: [0.22, 0.61, 0.36, 1] }}
      aria-hidden
    />
  );
}

export function StepsSection() {
  const reduceMotion = useReducedMotion();
  const sectionRef = useRef<HTMLElement>(null);
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(false);
  const [windBurst, setWindBurst] = useState(0);

  const step = steps[index];

  useEffect(() => {
    const node = sectionRef.current;
    if (!node) return undefined;

    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.45 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible || reduceMotion) return undefined;
    const timer = window.setInterval(() => {
      setWindBurst((value) => value + 1);
      setIndex((current) => (current + 1) % steps.length);
    }, STEP_MS);
    return () => window.clearInterval(timer);
  }, [visible, reduceMotion]);

  return (
    <section
      ref={sectionRef}
      className="relative flex min-h-[100svh] items-center justify-center overflow-hidden bg-[#f5f5f7]"
      aria-label="Как это работает"
    >
      <motion.div
        className="absolute inset-0"
        animate={{
          background: [
            "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(35,136,255,0.08), transparent 70%)",
            "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(99,102,241,0.07), transparent 70%)",
            "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(16,185,129,0.08), transparent 70%)",
          ][index],
        }}
        transition={{ duration: 1.2, ease: [0.25, 0.1, 0.25, 1] }}
        aria-hidden
      />

      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        <AnimatePresence mode="popLayout">
          {windBurst > 0 ? (
            <motion.div key={windBurst} className="absolute inset-0">
              <WindStreak delay={0} />
              <WindStreak delay={0.08} />
              <WindStreak delay={0.16} />
              <motion.span
                className="absolute left-1/2 top-[38%] h-24 w-[70vw] max-w-3xl -translate-x-1/2 rounded-full bg-white/40 blur-3xl"
                initial={{ x: 80, opacity: 0 }}
                animate={{ x: -120, opacity: [0, 0.7, 0] }}
                transition={{ duration: 0.95, ease: [0.22, 0.61, 0.36, 1] }}
              />
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      <div className="relative z-10 flex w-full max-w-4xl flex-col items-center px-6 text-center">
        <p className="mb-10 text-xs font-medium uppercase tracking-[0.28em] text-[var(--ar-stone)] sm:text-sm">
          Как это работает
        </p>

        <div className="relative flex h-[7.5rem] w-full items-center justify-center sm:h-[9rem]">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={step.title}
              className="absolute inset-0 flex flex-col items-center justify-center"
              initial={
                reduceMotion
                  ? { opacity: 0 }
                  : { opacity: 0, x: 72, filter: "blur(12px)", skewX: -4 }
              }
              animate={
                reduceMotion
                  ? { opacity: 1 }
                  : { opacity: 1, x: 0, filter: "blur(0px)", skewX: 0 }
              }
              exit={
                reduceMotion
                  ? { opacity: 0 }
                  : { opacity: 0, x: -88, filter: "blur(14px)", skewX: 6 }
              }
              transition={{ duration: 0.85, ease: [0.22, 0.61, 0.36, 1] }}
            >
              <h2 className="text-5xl font-semibold tracking-[-0.04em] text-[var(--ar-black)] sm:text-7xl md:text-8xl">
                {step.title}
              </h2>
              <p className="mt-4 text-base text-[var(--ar-mist)] sm:text-lg">{step.hint}</p>
            </motion.div>
          </AnimatePresence>
        </div>

        <div className="mt-14 flex items-center gap-2">
          {steps.map((item, itemIndex) => (
            <button
              key={item.title}
              type="button"
              onClick={() => {
                setIndex(itemIndex);
                setWindBurst((value) => value + 1);
              }}
              className="group p-2"
              aria-label={item.title}
              aria-current={itemIndex === index ? "step" : undefined}
            >
              <span
                className={`block h-1 rounded-full transition-all duration-500 ${
                  itemIndex === index
                    ? "w-8 bg-[var(--ar-black)]"
                    : "w-2 bg-black/15 group-hover:bg-black/30"
                }`}
              />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
