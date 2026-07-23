"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { LandingSection } from "@/components/landing/section";
import { LOGIN_HREF, finalCtaCopy } from "@/lib/landing/content";
import { trackLandingEvent } from "@/lib/landing/analytics";

export function FinalCtaSection() {
  return (
    <LandingSection tone="ink" className="border-t-0" ariaLabelledBy="final-cta-title">
      <div className="mx-auto max-w-3xl text-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--ar-cyan)]">
          Готовы начать
        </p>
        <h2
          id="final-cta-title"
          className="mt-4 text-balance text-3xl font-semibold tracking-[-0.035em] text-white sm:text-5xl sm:leading-[1.08]"
        >
          {finalCtaCopy.title}
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-white/65 sm:text-lg">
          {finalCtaCopy.subtitle}
        </p>
        <div className="mt-8 flex flex-col items-center gap-4">
          <Link
            href={LOGIN_HREF}
            onClick={() => trackLandingEvent("final_start_project")}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-[0.65rem] bg-white px-7 text-sm font-semibold text-[var(--ar-black)] transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-cyan)]/50"
          >
            {finalCtaCopy.primaryCta}
            <ArrowRight size={16} aria-hidden />
          </Link>
          <Link
            href={LOGIN_HREF}
            className="text-sm font-medium text-white/70 underline-offset-4 transition-colors hover:text-white hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-cyan)]/40"
          >
            {finalCtaCopy.secondaryCta}
          </Link>
        </div>
      </div>
    </LandingSection>
  );
}
