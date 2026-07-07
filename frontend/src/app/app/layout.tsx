"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppSidebar } from "@/components/app/app-sidebar";
import { AppMobileHeader, AppMobileNav } from "@/components/app/app-mobile-nav";
import { OnboardingTour } from "@/components/app/onboarding-tour";
import { PageLoader } from "@/components/ui/loader";
import { getAccessToken } from "@/lib/auth";
import { getMe, logout, refreshSession, completeOnboarding } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [isChecking, setIsChecking] = useState(true);
  const [credits, setCredits] = useState(0);
  const [onboardingCompleted, setOnboardingCompleted] = useState(true);

  useEffect(() => {
    const verifySession = async () => {
      const token = getAccessToken();
      if (!token) {
        const refreshed = await refreshSession();
        if (!refreshed) {
          router.replace("/auth/login");
          return;
        }
      }
      try {
        const me = await getMe();
        setCredits(me.credits_balance);
        setOnboardingCompleted(me.onboarding_completed);
      } catch {
        router.replace("/auth/login");
        return;
      }
      setIsChecking(false);
    };
    void verifySession();
  }, [router]);

  const onLogout = async () => {
    await logout();
    router.replace("/auth/login");
  };

  if (isChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center atmosphere">
        <PageLoader />
      </div>
    );
  }

  return (
    <div className="min-h-screen atmosphere text-[var(--ar-black)]">
      <div className="fixed inset-0 atmosphere-grid" aria-hidden />
      <AppSidebar credits={credits} onLogout={onLogout} />
      <AppMobileHeader credits={credits} />
      <AppMobileNav credits={credits} onLogout={onLogout} />
      <main data-tour="app-workspace" className="relative z-10 min-h-screen px-4 pb-24 pt-20 lg:ml-72 lg:p-8">
        {children}
      </main>
      <OnboardingTour
        completed={onboardingCompleted}
        onComplete={async () => {
          try {
            const me = await completeOnboarding();
            setOnboardingCompleted(me.onboarding_completed);
          } catch {
            setOnboardingCompleted(true);
          }
        }}
      />
    </div>
  );
}
