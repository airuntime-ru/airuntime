import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { ProcessDemo } from "@/components/landing/process-demo";
import { LOGIN_HREF, PROCESS_ANCHOR, heroCopy } from "@/lib/landing/content";

export function HeroSection() {
  return (
    <section className="relative overflow-hidden" aria-labelledby="hero-title">
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden
        style={{
          background:
            "radial-gradient(ellipse 65% 50% at 88% 8%, rgba(47,124,255,0.09), transparent 58%)",
        }}
      />

      <div className="relative mx-auto grid max-w-6xl gap-10 px-5 pb-14 pt-10 sm:px-8 sm:pb-16 sm:pt-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.95fr)] lg:items-center lg:gap-14 lg:pb-20 lg:pt-14">
        <div className="max-w-[37rem]">
          <p className="text-sm font-medium text-[var(--ar-sky)]">Idea → Build → Runtime</p>
          <h1
            id="hero-title"
            className="mt-4 text-balance text-[2.65rem] font-semibold leading-[1.08] tracking-[-0.035em] text-[var(--ar-black)] sm:text-[3.25rem] lg:text-[4.25rem] lg:leading-[1.05]"
          >
            {heroCopy.titleLine1}
            <br />
            {heroCopy.titleLine2}
          </h1>
          <p className="mt-5 max-w-[34rem] text-lg leading-relaxed text-[var(--ar-mist)] sm:text-xl">
            {heroCopy.subtitle}
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Link
              href={LOGIN_HREF}
              className="inline-flex h-12 items-center justify-center gap-2 rounded-[0.65rem] bg-[var(--ar-black)] px-6 text-sm font-semibold text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/40"
            >
              {heroCopy.primaryCta}
              <ArrowRight size={16} aria-hidden />
            </Link>
            <a
              href={PROCESS_ANCHOR}
              className="inline-flex h-12 items-center justify-center rounded-[0.65rem] px-6 text-sm font-semibold text-[var(--ar-graphite)] transition-colors hover:text-[var(--ar-black)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35"
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
