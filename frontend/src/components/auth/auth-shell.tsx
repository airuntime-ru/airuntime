"use client";

import type { ReactNode } from "react";
import Link from "next/link";

import { InteractiveBackground } from "@/components/landing/interactive-background";
import { Logo } from "@/components/brand/logo";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <InteractiveBackground />
      <div className="relative z-10 mx-auto grid min-h-screen max-w-5xl items-center gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[0.9fr_1fr] lg:px-8">
        <div className="hidden lg:block">
          <Logo href="/" variant="stacked" theme="dark" size="lg" />
          <h1 className="mt-8 max-w-md text-4xl font-semibold leading-tight tracking-tight text-[var(--ar-black)]">
            Войдите и продолжите собирать проекты
          </h1>
          <p className="mt-4 max-w-md text-base leading-relaxed text-[var(--ar-mist)]">
            Одноразовый код по почте, без лишних паролей. Кабинет откроет проекты, чаты, секреты и деплои.
          </p>
        </div>
        <div className="mx-auto w-full max-w-md">
          <div className="mb-8 flex justify-center lg:hidden">
            <Logo href="/" variant="full" theme="dark" size="md" />
          </div>
          <div className="glass rounded-[var(--ar-radius-sm)] p-6 shadow-[0_30px_100px_rgba(56,112,180,0.16)] sm:p-8">
            {children}
          </div>
          <p className="mt-5 text-center text-xs text-[var(--ar-stone)]">
            Вернуться на{" "}
            <Link href="/" className="font-medium text-[var(--ar-sky)] hover:underline">
              лендинг AIRuntime
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
