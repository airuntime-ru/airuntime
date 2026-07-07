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
    <main className="relative min-h-screen overflow-hidden">
      <InteractiveBackground />
      <div className="relative z-10 mx-auto flex max-w-6xl flex-col gap-24 px-6 py-8 md:gap-32 md:px-10">
        <header className="flex items-center justify-between pt-4">
          <Logo href="/" variant="full" theme="dark" size="md" priority />
          <div className="flex gap-2">
            <Link href="/auth/login">
              <Button variant="ghost" size="sm">
                Войти
              </Button>
            </Link>
            <Link href="/auth/login">
              <Button variant="accent" size="sm">
                Начать
              </Button>
            </Link>
          </div>
        </header>

        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="grid min-h-[78vh] items-center gap-10 lg:grid-cols-2"
        >
          <div>
            <p className="mb-4 text-sm uppercase tracking-[0.3em] text-[var(--ar-sky)]">Сложность растворяется в воздухе</p>
            <h1 className="text-5xl font-semibold leading-[1.02] text-[var(--ar-cloud)] md:text-7xl">
              Опишите.
              <br />
              <span className="text-gradient">Мы воплотим.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg text-[var(--ar-mist)]">
              AIRuntime превращает идеи в работающие приложения. Вы остаётесь в потоке — агенты планируют, пишут код и запускают.
            </p>
            <div className="mt-10 flex flex-wrap gap-3">
              <Link href="/auth/login">
                <Button variant="accent" size="lg">
                  Начать
                </Button>
              </Link>
              <Link href="/app">
                <Button variant="outline" size="lg">
                  Открыть кабинет
                </Button>
              </Link>
            </div>
          </div>
          <ProductPreview />
        </motion.section>

        <StepsSection />
        <AirSection />

        <section className="pb-20 pt-8 text-center">
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-3xl font-light text-[var(--ar-cloud)] md:text-5xl"
          >
            Свобода создавать
          </motion.h2>
          <Link href="/auth/login" className="mt-10 inline-block">
            <Button variant="accent" size="lg">
              Войти по почте
            </Button>
          </Link>
        </section>

        <footer className="pb-8 text-center text-sm text-[var(--ar-stone)]">
          AIRuntime — идеи становятся живыми продуктами
        </footer>
      </div>
    </main>
  );
}
