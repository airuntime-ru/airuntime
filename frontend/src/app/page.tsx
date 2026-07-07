"use client";

import Link from "next/link";
import { motion } from "framer-motion";

import { AirSection } from "@/components/landing/air-section";
import { InteractiveBackground } from "@/components/landing/interactive-background";
import { ProductPreview } from "@/components/landing/product-preview";
import { StepsSection } from "@/components/landing/steps-section";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-x-hidden">
      <InteractiveBackground />
      <div className="relative z-10 mx-auto flex max-w-6xl flex-col gap-14 px-4 py-5 sm:gap-20 sm:px-6 sm:py-8 md:gap-32 md:px-10">
        <header className="flex items-center justify-between gap-3 pt-1 sm:pt-4">
          <Logo href="/" variant="full" theme="dark" size="sm" priority className="sm:hidden" />
          <Logo href="/" variant="full" theme="dark" size="md" priority className="hidden sm:block" />
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            <Link href="/auth/login" className="hidden sm:block">
              <Button variant="ghost" size="sm">
                Войти
              </Button>
            </Link>
            <Link href="/auth/login">
              <Button variant="accent" size="sm" className="px-4 sm:px-3">
                Начать
              </Button>
            </Link>
          </div>
        </header>

        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="grid items-center gap-8 sm:gap-10 lg:min-h-[78vh] lg:grid-cols-2 lg:gap-12"
        >
          <div className="order-1 text-center lg:text-left">
            <p className="mb-3 text-[0.65rem] uppercase tracking-[0.22em] text-[var(--ar-sky)] sm:mb-4 sm:text-sm sm:tracking-[0.3em]">
              Сложность растворяется в воздухе
            </p>
            <h1 className="text-[2.35rem] font-semibold leading-[1.05] text-[var(--ar-cloud)] sm:text-5xl md:text-7xl">
              Опишите.
              <br />
              <span className="text-gradient">Мы воплотим.</span>
            </h1>
            <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-[var(--ar-mist)] sm:mt-6 sm:text-lg lg:mx-0">
              AIRuntime превращает идеи в готовые приложения. Опишите задачу — мы соберём и запустим.
            </p>
            <div className="mt-7 flex flex-col gap-2.5 sm:mt-10 sm:flex-row sm:flex-wrap sm:justify-center sm:gap-3 lg:justify-start">
              <Link href="/auth/login" className="w-full sm:w-auto">
                <Button variant="accent" size="lg" className="w-full sm:w-auto">
                  Начать
                </Button>
              </Link>
              <Link href="/app" className="w-full sm:w-auto">
                <Button variant="outline" size="lg" className="w-full sm:w-auto">
                  Открыть кабинет
                </Button>
              </Link>
            </div>
          </div>
          <div className="order-2 w-full max-w-md justify-self-center lg:max-w-none lg:justify-self-end">
            <ProductPreview />
          </div>
        </motion.section>

        <StepsSection />
        <AirSection />

        <section className="pb-12 pt-4 text-center sm:pb-20 sm:pt-8">
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-2xl font-light text-[var(--ar-cloud)] sm:text-3xl md:text-5xl"
          >
            Свобода создавать
          </motion.h2>
          <Link href="/auth/login" className="mt-7 inline-block w-full max-w-xs sm:mt-10 sm:w-auto">
            <Button variant="accent" size="lg" className="w-full sm:w-auto">
              Войти по почте
            </Button>
          </Link>
        </section>

        <footer className="pb-6 text-center text-xs text-[var(--ar-stone)] sm:pb-8 sm:text-sm">
          AIRuntime — идеи становятся живыми продуктами
        </footer>
      </div>
    </main>
  );
}
