"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { ProcessDemo } from "@/components/landing/process-demo";
import { LOGIN_HREF, PROCESS_ANCHOR, heroCopy } from "@/lib/landing/content";
import { trackLandingEvent } from "@/lib/landing/analytics";

export function HeroSection() {
  return (
    <section
      className="relative overflow-hidden border-b border-black/[0.06]"
      aria-labelledby="hero-title"
    >
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden
        style={{
          background:
            "radial-gradient(ellipse 70% 55% at 85% 10%, rgba(35,136,255,0.10), transparent 60%), radial-gradient(ellipse 50% 40% at 8% 90%, rgba(25,199,210,0.07), transparent 55%)",
        }}
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[var(--ar-sky)]/35 to-transparent"
        aria-hidden
      />

      <div className="relative mx-auto grid max-w-6xl gap-10 px-5 pb-14 pt-10 sm:px-8 sm:pb-16 sm:pt-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:items-center lg:gap-12 lg:pb-20 lg:pt-14">
        <div className="max-w-xl">
          <p className="inline-flex items-center gap-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--ar-sky)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--ar-sky)]" aria-hidden />
            Idea → Build → Runtime
          </p>
          <h1
            id="hero-title"
            className="mt-4 text-balance text-[2.15rem] font-semibold leading-[1.08] tracking-[-0.035em] text-[var(--ar-black)] sm:text-5xl sm:leading-[1.05] lg:text-[3.15rem]"
          >
            {heroCopy.titleLine1}
            <br />
            {heroCopy.titleLine2}
          </h1>
          <p className="mt-5 max-w-md text-base leading-relaxed text-[var(--ar-mist)] sm:text-lg">
            {heroCopy.subtitle}
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Link
              href={LOGIN_HREF}
              onClick={() => trackLandingEvent("hero_start_project", { source: "hero" })}
              className="inline-flex h-12 items-center justify-center gap-2 rounded-[0.65rem] bg-[var(--ar-black)] px-6 text-sm font-semibold text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/40"
            >
              {heroCopy.primaryCta}
              <ArrowRight size={16} aria-hidden />
            </Link>
            <a
              href={PROCESS_ANCHOR}
              onClick={() => trackLandingEvent("hero_view_process")}
              className="inline-flex h-12 items-center justify-center rounded-[0.65rem] border border-black/12 bg-white px-6 text-sm font-semibold text-[var(--ar-graphite)] transition-colors hover:border-[var(--ar-sky)]/35 hover:bg-[rgba(35,136,255,0.04)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35"
            >
              {heroCopy.secondaryCta}
            </a>
          </div>
        </div>

        <ProcessDemo />
      </div>
    </section>
  );
}
