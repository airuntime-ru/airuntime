"use client";

import { motion } from "framer-motion";

const steps = [
  "Опишите задачу",
  "AI собирает продукт",
  "Запуск в рантайме",
];

export function StepsSection() {
  return (
    <section className="py-10 md:py-16">
      <div className="flex flex-col items-center gap-10 md:flex-row md:justify-center md:gap-20">
        {steps.map((step, index) => (
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: index * 0.1 }}
            className="text-center"
          >
            <p className="mb-3 text-xs tracking-[0.35em] text-[var(--ar-sky)]">0{index + 1}</p>
            <p className="text-lg text-[var(--ar-cloud)] md:text-xl">{step}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
