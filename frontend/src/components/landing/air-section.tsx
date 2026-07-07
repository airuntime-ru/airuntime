"use client";

import { motion } from "framer-motion";

const lines = [
  "Опишите идею — остальное в воздухе.",
  "Мы собираем, проверяем и запускаем.",
  "Без серверов и сложных настроек. Только разговор — и готовый результат.",
];

export function AirSection() {
  return (
    <section className="relative py-10 sm:py-20 md:py-32">
      <div className="mx-auto max-w-3xl space-y-8 px-1 text-center sm:space-y-12 md:space-y-16">
        {lines.map((line, index) => (
          <motion.p
            key={line}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.8, delay: index * 0.12, ease: [0.22, 1, 0.36, 1] }}
            className="text-xl font-light leading-relaxed text-[var(--ar-mist)] sm:text-2xl md:text-4xl md:leading-snug"
          >
            {line}
          </motion.p>
        ))}
      </div>
    </section>
  );
}
