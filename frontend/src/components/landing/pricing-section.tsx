import { Check } from "lucide-react";
import Link from "next/link";

import { LandingSection, SectionHeading } from "@/components/landing/section";
import { Reveal } from "@/components/ui/reveal";
import { LOGIN_HREF } from "@/lib/landing/content";
import { cn } from "@/lib/cn";

type PublicPlan = {
  key: string;
  name: string;
  price_rub: number;
  monthly_budget_rub: number;
  max_projects: number;
  max_concurrent_projects: number;
  grant_renews: boolean;
  allowed_models: string[] | null;
};

/**
 * Mirrors the seeded plans so the page still renders if the API is unreachable at build time.
 * Kept in sync with migration 0021's PLAN_DEFAULTS.
 */
const FALLBACK_PLANS: PublicPlan[] = [
  {
    key: "free",
    name: "Бесплатный",
    price_rub: 0,
    monthly_budget_rub: 100,
    max_projects: 1,
    max_concurrent_projects: 1,
    grant_renews: false,
    allowed_models: ["gpt-5.6-luna"],
  },
  {
    key: "pro",
    name: "Про",
    price_rub: 990,
    monthly_budget_rub: 700,
    max_projects: 10,
    max_concurrent_projects: 5,
    grant_renews: true,
    allowed_models: null,
  },
  {
    key: "business",
    name: "Бизнес",
    price_rub: 2990,
    monthly_budget_rub: 2200,
    max_projects: 50,
    max_concurrent_projects: 20,
    grant_renews: true,
    allowed_models: null,
  },
];

async function loadPlans(): Promise<PublicPlan[]> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) return FALLBACK_PLANS;
  try {
    const response = await fetch(`${base}/billing/plans`, { next: { revalidate: 300 } });
    if (!response.ok) return FALLBACK_PLANS;
    const rows = (await response.json()) as PublicPlan[];
    return rows.length ? rows : FALLBACK_PLANS;
  } catch {
    // The landing must never fail to render because billing is down.
    return FALLBACK_PLANS;
  }
}

// "до N проектов": genitive throughout, so only N=1 differs ("1 проекта" vs "5 проектов").
function pluralizeProjects(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  return mod10 === 1 && mod100 !== 11 ? "проекта" : "проектов";
}

function planFeatures(plan: PublicPlan): string[] {
  const budget = plan.grant_renews
    ? `${plan.monthly_budget_rub} ₽ на модели каждый месяц`
    : `${plan.monthly_budget_rub} ₽ на модели — разово при регистрации`;
  return [
    budget,
    plan.max_projects > 0
      ? `До ${plan.max_projects} ${pluralizeProjects(plan.max_projects)}`
      : "Проекты без ограничений",
    `До ${plan.max_concurrent_projects} запущено одновременно`,
    plan.allowed_models
      ? "Экономичная модель"
      : "Все модели, включая самую сильную",
    "Свой домен",
    "Свой API-ключ — токены без списаний",
  ];
}

export async function PricingSection() {
  const plans = await loadPlans();

  return (
    <LandingSection id="pricing" ariaLabelledBy="pricing-title" tone="muted">
      <SectionHeading
        eyebrow="Тарифы"
        title="Начните бесплатно"
        description="На старте — 100 ₽ на модели. Дальше пополняете баланс или переходите на тариф."
        id="pricing-title"
        align="center"
      />

      <ul className="mt-14 grid gap-5 lg:grid-cols-3">
        {plans.map((plan, index) => {
          const highlighted = plan.key === "pro";
          return (
            <Reveal as="li" key={plan.key} delay={index * 90}>
              <article
                className={cn(
                  "sky-card sky-card-hover flex h-full flex-col rounded-[1.1rem] p-6 sm:p-7",
                  highlighted && "border-[rgba(35,136,255,0.3)] shadow-[0_24px_60px_-30px_rgba(35,136,255,0.55)]"
                )}
              >
                {highlighted ? (
                  <p className="mb-3 inline-flex w-fit rounded-full bg-[image:var(--ar-accent-gradient)] px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-white">
                    Популярный
                  </p>
                ) : null}
                <h3 className="text-lg font-semibold tracking-[-0.02em] text-[var(--ar-black)]">
                  {plan.name}
                </h3>
                <p className="mt-3 text-[2rem] font-semibold leading-none tracking-[-0.03em] text-[var(--ar-black)]">
                  {plan.price_rub > 0 ? (
                    <>
                      {plan.price_rub.toLocaleString("ru-RU")}
                      <span className="ml-1.5 text-base font-medium text-[var(--ar-stone)]">
                        ₽/мес
                      </span>
                    </>
                  ) : (
                    "Бесплатно"
                  )}
                </p>

                <ul className="mt-6 flex-1 space-y-2.5">
                  {planFeatures(plan).map((feature) => (
                    <li
                      key={feature}
                      className="flex items-start gap-2.5 text-[0.92rem] leading-relaxed text-[var(--ar-mist)]"
                    >
                      <Check size={15} className="mt-1 shrink-0 text-emerald-500" aria-hidden />
                      {feature}
                    </li>
                  ))}
                </ul>

                <Link href={LOGIN_HREF} className="mt-7">
                  <span
                    className={cn(
                      "flex h-11 items-center justify-center rounded-[0.7rem] text-sm font-semibold transition-colors",
                      highlighted
                        ? "btn-glow"
                        : "border border-black/[0.08] bg-white text-[var(--ar-graphite)] hover:border-[var(--ar-sky)]/35 hover:text-[var(--ar-black)]"
                    )}
                  >
                    {plan.price_rub > 0 ? "Оставить заявку" : "Начать бесплатно"}
                  </span>
                </Link>
              </article>
            </Reveal>
          );
        })}
      </ul>

      <Reveal delay={180}>
        <p className="mx-auto mt-8 max-w-2xl text-center text-sm leading-relaxed text-[var(--ar-stone)]">
          Платный тариф подключается после подтверждения оплаты — заявка отправляется из кабинета.
          Баланс можно пополнить отдельно в любой момент.
        </p>
      </Reveal>
    </LandingSection>
  );
}
