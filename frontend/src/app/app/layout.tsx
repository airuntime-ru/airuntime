"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AppMobileNav } from "@/components/app/app-mobile-nav";
import { AppTopBar } from "@/components/app/app-topbar";
import { CreateProjectProvider } from "@/components/app/create-project-context";
import { OnboardingTour } from "@/components/app/onboarding-tour";
import { PageLoader } from "@/components/ui/loader";
import { getAccessToken } from "@/lib/auth";
import { completeOnboarding, getMe, logout, refreshSession } from "@/lib/api";
import { cn } from "@/lib/cn";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isProjectRoute = Boolean(pathname?.match(/^\/app\/projects\/[^/]+/));
  const isFullHeightRoute = isProjectRoute;
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
      <div className="app-shell flex min-h-screen items-center justify-center">
        <PageLoader />
      </div>
    );
  }

  return (
    // Deliberately static decoration: this shell mounts on every authenticated page, so the
    // backdrop is a gradient plus a tiled dust texture - one paint, no running animation.
    <CreateProjectProvider>
      <div className="app-shell stardust isolate min-h-screen text-[var(--ar-black)]">
        <AppTopBar credits={credits} onLogout={onLogout} />
        <AppMobileNav onLogout={onLogout} />
        {/* The chat is a fixed-viewport workspace: main gets a definite height there so the
            flex chain can shrink the transcript and keep the composer on screen. Everywhere
            else main just grows and the page scrolls normally. Sizing it with
            calc(100dvh - Nrem) instead silently breaks whenever the header height changes. */}
        <main
          data-tour="app-workspace"
          className={cn(
            "relative z-10 flex flex-col px-3 pb-28 pt-[5.5rem] sm:px-4 lg:px-6 lg:pb-10",
            isFullHeightRoute ? "h-dvh overflow-hidden" : "min-h-screen"
          )}
        >
          {/* min-h-0 on every level of the chain: a flex item defaults to min-height:auto and
              refuses to shrink below its content, which is what lets the chat overflow. */}
          <div
            className={cn(
              "mx-auto flex min-h-0 w-full flex-1 flex-col",
              isProjectRoute ? "max-w-[96rem]" : "max-w-6xl"
            )}
          >
            {children}
          </div>
        </main>
        <OnboardingTour
          completed={onboardingCompleted}
          onLogout={onLogout}
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
    </CreateProjectProvider>
  );
}
