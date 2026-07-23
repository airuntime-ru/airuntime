import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { LandingSection } from "@/components/landing/section";
import { LOGIN_HREF, finalCtaCopy } from "@/lib/landing/content";

export function FinalCtaSection() {
  return (
    <LandingSection tone="ink" ariaLabelledBy="final-cta-title">
      <div className="mx-auto max-w-2xl text-center">
        <h2
          id="final-cta-title"
          className="text-balance text-[2rem] font-semibold tracking-[-0.03em] text-white sm:text-[2.5rem] sm:leading-[1.15]"
        >
          {finalCtaCopy.title}
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-white/65 sm:text-lg">
          {finalCtaCopy.subtitle}
        </p>
        <div className="mt-8 flex flex-col items-center gap-4">
          <Link
            href={LOGIN_HREF}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-[0.65rem] bg-white px-7 text-sm font-semibold text-[var(--ar-black)] transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
          >
            {finalCtaCopy.primaryCta}
            <ArrowRight size={16} aria-hidden />
          </Link>
          <Link
            href={LOGIN_HREF}
            className="text-sm font-medium text-white/70 underline-offset-4 transition-colors hover:text-white hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
          >
            {finalCtaCopy.secondaryCta}
          </Link>
        </div>
      </div>
    </LandingSection>
  );
}
