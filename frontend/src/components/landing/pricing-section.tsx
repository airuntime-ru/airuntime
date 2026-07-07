import Link from "next/link";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const tiers = [
  {
    name: "Start",
    price: "0 ₽",
    detail: "Чтобы попробовать идею и собрать первый проект.",
    points: ["1 проект", "чат с контекстом", "первый деплой"],
  },
  {
    name: "Builder",
    price: "по запросу",
    detail: "Для основателей и команд, которые регулярно запускают новые продукты.",
    points: ["несколько проектов", "секреты и деплои", "приоритетная сборка"],
    featured: true,
  },
  {
    name: "Team",
    price: "индивидуально",
    detail: "Для рабочих пространств, ролей и production-настроек.",
    points: ["командный доступ", "домены", "расширенная поддержка"],
  },
];

export function PricingSection() {
  return (
    <section className="py-10 sm:py-16">
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-cyan)]">Старт</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">
            Начните с одного проекта
          </h2>
        </div>
        <p className="max-w-md text-sm leading-relaxed text-[var(--ar-mist)]">
          Цены можно менять позже. Главное сейчас — быстро почувствовать, что идея становится работающим продуктом.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {tiers.map((tier) => (
          <Card
            key={tier.name}
            className={tier.featured ? "border-[var(--ar-border-strong)] bg-white" : "bg-white/75"}
            hover={Boolean(tier.featured)}
          >
            <p className="text-sm font-semibold text-[var(--ar-sky)]">{tier.name}</p>
            <p className="mt-3 text-3xl font-semibold text-[var(--ar-black)]">{tier.price}</p>
            <p className="mt-3 min-h-14 text-sm leading-relaxed text-[var(--ar-mist)]">{tier.detail}</p>
            <div className="mt-5 space-y-2">
              {tier.points.map((point) => (
                <div key={point} className="flex items-center gap-2 text-sm text-[var(--ar-graphite)]">
                  <Check size={15} className="text-emerald-500" />
                  <span>{point}</span>
                </div>
              ))}
            </div>
            <Link href="/auth/login" className="mt-6 block">
              <Button variant={tier.featured ? "accent" : "outline"} className="w-full">
                Начать
              </Button>
            </Link>
          </Card>
        ))}
      </div>
    </section>
  );
}
