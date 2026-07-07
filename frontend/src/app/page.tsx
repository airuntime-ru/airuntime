"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

import { FaqSection } from "@/components/landing/faq-section";
import { ProductPreview } from "@/components/landing/product-preview";
import { StepsSection } from "@/components/landing/steps-section";
import { Logo } from "@/components/brand/logo";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#fbfbfd] text-[var(--ar-black)]">
      <div className="mx-auto flex max-w-5xl flex-col px-5 sm:px-8">
        <header className="flex items-center justify-between py-5 sm:py-6">
          <Logo href="/" variant="full" theme="dark" size="sm" priority />
          <Link
            href="/auth/login"
            className="text-sm font-medium text-[var(--ar-sky)] transition-opacity hover:opacity-70"
          >
            Войти
          </Link>
        </header>

        <section className="flex flex-col items-center pb-16 pt-10 text-center sm:pb-24 sm:pt-16">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
            className="max-w-3xl"
          >
            <h1 className="text-[2.5rem] font-semibold leading-[1.05] tracking-[-0.03em] sm:text-6xl sm:leading-[1.02]">
              Опишите идею.
              <br />
              Получите проект.
            </h1>
            <p className="mx-auto mt-5 max-w-md text-base leading-relaxed text-[var(--ar-mist)] sm:text-lg">
              Сайт или Telegram-бот — в одном чате.
            </p>
            <Link
              href="/auth/login"
              className="mt-8 inline-flex h-12 items-center justify-center gap-2 rounded-full bg-[var(--ar-black)] px-7 text-sm font-medium text-white transition-transform hover:scale-[1.02] active:scale-[0.98]"
            >
              Запустить проект
              <ArrowRight size={16} />
            </Link>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12, duration: 0.7, ease: [0.25, 0.1, 0.25, 1] }}
            className="mt-14 w-full max-w-2xl sm:mt-16"
          >
            <ProductPreview />
          </motion.div>
        </section>

        <StepsSection />
        <FaqSection />

        <footer className="border-t border-black/[0.06] py-10 text-center text-xs text-[var(--ar-stone)]">
          AIRuntime
        </footer>
      </div>
    </main>
  );
}
