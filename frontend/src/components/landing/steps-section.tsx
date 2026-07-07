"use client";

import { motion } from "framer-motion";

const steps = [
  { title: "Опишите задачу", hint: "Одним сообщением — что нужно сделать" },
  { title: "Собираем приложение", hint: "Проверяем и доводим до ума" },
  { title: "Публикуем", hint: "Рабочая ссылка — можно сразу делиться" },
];

export function StepsSection() {
  return (
    <section className="py-4 sm:py-10 md:py-16">
      <div className="relative mx-auto max-w-md sm:max-w-none">
        <div className="absolute bottom-4 left-[1.15rem] top-4 w-px bg-gradient-to-b from-[var(--ar-sky)]/50 via-[var(--ar-border)] to-transparent sm:hidden" />

        <div className="flex flex-col gap-6 sm:flex-row sm:justify-center sm:gap-12 md:gap-20">
          {steps.map((step, index) => (
            <motion.div
              key={step.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: index * 0.1 }}
              className="relative pl-10 text-left sm:pl-0 sm:text-center"
            >
              <span className="absolute left-0 top-0.5 flex h-9 w-9 items-center justify-center rounded-full border border-[var(--ar-border-strong)] bg-[var(--ar-surface-2)] text-[0.65rem] font-medium tracking-wider text-[var(--ar-sky)] sm:static sm:mx-auto sm:mb-3 sm:h-auto sm:w-auto sm:border-0 sm:bg-transparent sm:p-0 sm:text-xs sm:tracking-[0.35em]">
                0{index + 1}
              </span>
              <p className="text-base font-medium text-[var(--ar-cloud)] sm:text-lg md:text-xl">{step.title}</p>
              <p className="mt-1 text-sm leading-snug text-[var(--ar-stone)] sm:mt-0 sm:hidden">{step.hint}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
