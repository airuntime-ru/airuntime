import { ArrowRight, CheckCircle2 } from "lucide-react";

import { Card } from "@/components/ui/card";

export function ComparisonSection() {
  return (
    <section className="py-10 sm:py-16">
      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr] lg:items-stretch">
        <div className="flex flex-col justify-center">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">Новый процесс</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">
            Меньше ручной рутины, больше движения к продукту
          </h2>
          <p className="mt-4 text-base leading-relaxed text-[var(--ar-mist)]">
            Вместо цепочки из подрядчиков, серверов и разрозненных инструментов вы работаете в одном понятном кабинете.
          </p>
        </div>
        <Card hover={false} className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-[var(--ar-radius-sm)] border border-[var(--ar-border)] bg-white/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--ar-stone)]">Обычно</p>
            <div className="mt-4 space-y-3 text-sm text-[var(--ar-mist)]">
              {["идея", "ТЗ", "код", "сервер", "деплой", "исправления"].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <ArrowRight size={14} className="text-[var(--ar-stone)]" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-[var(--ar-radius-sm)] border border-[var(--ar-border-strong)] bg-white p-4 shadow-sm shadow-sky-950/5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--ar-sky)]">AIRuntime</p>
            <div className="mt-4 space-y-3 text-sm text-[var(--ar-graphite)]">
              {["идея", "диалог", "готовая ссылка"].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <CheckCircle2 size={15} className="text-emerald-500" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>
    </section>
  );
}
