"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, PlayCircle } from "lucide-react";

import { AirSection } from "@/components/landing/air-section";
import { ComparisonSection } from "@/components/landing/comparison-section";
import { FaqSection } from "@/components/landing/faq-section";
import { FeaturesSection } from "@/components/landing/features-section";
import { InteractiveBackground } from "@/components/landing/interactive-background";
import { PricingSection } from "@/components/landing/pricing-section";
import { ProductPreview } from "@/components/landing/product-preview";
import { StepsSection } from "@/components/landing/steps-section";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-x-hidden">
      <InteractiveBackground />
      <div className="relative z-10 mx-auto flex max-w-6xl flex-col px-4 py-5 sm:px-6 sm:py-8 md:px-10">
        <header className="flex items-center justify-between gap-3">
          <Logo href="/" variant="full" theme="dark" size="sm" priority />
          <div className="flex shrink-0 items-center gap-2">
            <Link href="/auth/login" className="hidden sm:block">
              <Button variant="ghost" size="sm">
                Войти
              </Button>
            </Link>
            <Link href="/auth/login">
              <Button variant="accent" size="sm" className="px-4">
                Начать
              </Button>
            </Link>
          </div>
        </header>

        <section className="flex min-h-[calc(100svh-5rem)] flex-col items-center justify-center gap-8 py-12 text-center sm:gap-10 md:py-16">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto max-w-4xl"
          >
            <p className="mb-4 text-xs font-semibold uppercase tracking-[0.28em] text-[var(--ar-sky)] sm:text-sm">
              AI Runtime для быстрых запусков
            </p>
            <h1 className="text-[2.8rem] font-semibold leading-[0.98] tracking-tight text-[var(--ar-black)] sm:text-6xl md:text-7xl">
              Создавайте проекты
              <br />
              <span className="text-gradient">так же легко, как описываете идею</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-[var(--ar-mist)] sm:text-lg">
              AIRuntime превращает запрос в рабочее приложение: планирует, собирает, деплоит и оставляет понятный кабинет для дальнейших изменений.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
              <Link href="/auth/login" className="w-full sm:w-auto">
                <Button variant="accent" size="lg" className="w-full sm:w-auto">
                  Создать проект
                  <ArrowRight size={18} />
                </Button>
              </Link>
              <Link href="/app" className="w-full sm:w-auto">
                <Button variant="outline" size="lg" className="w-full sm:w-auto">
                  <PlayCircle size={18} />
                  Открыть кабинет
                </Button>
              </Link>
            </div>
          </motion.div>

          <div className="w-full max-w-2xl">
            <ProductPreview />
          </div>
        </section>

        <StepsSection />
        <FeaturesSection />
        <AirSection />
        <ComparisonSection />
        <PricingSection />
        <FaqSection />

        <section className="py-12 text-center sm:py-20">
          <h2 className="mx-auto max-w-3xl text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-5xl">
            Первый проект может появиться уже сегодня
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-[var(--ar-mist)] sm:text-base">
            Начните с короткого описания. AIRuntime превратит его в конкретный план и рабочий результат.
          </p>
          <Link href="/auth/login" className="mt-8 inline-block w-full max-w-xs sm:w-auto">
            <Button variant="accent" size="lg" className="w-full sm:w-auto">
              Войти по почте
              <ArrowRight size={18} />
            </Button>
          </Link>
        </section>

        <footer className="border-t border-[var(--ar-border)] py-8 text-center text-xs text-[var(--ar-stone)] sm:text-sm">
          AIRuntime · идеи становятся живыми продуктами
        </footer>
      </div>
    </main>
  );
}
