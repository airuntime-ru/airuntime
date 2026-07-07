"use client";

import type { ReactNode } from "react";

import { InteractiveBackground } from "@/components/landing/interactive-background";
import { Logo } from "@/components/brand/logo";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <InteractiveBackground />
      <div className="relative z-10 mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 py-12">
        <Logo href="/" variant="full" theme="dark" size="lg" className="mb-10" />
        <div className="glass w-full rounded-[var(--ar-radius-xl)] border border-white/10 p-8 shadow-[0_30px_120px_rgba(94,184,255,0.08)]">
          {children}
        </div>
      </div>
    </div>
  );
}
