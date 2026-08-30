"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import { getMe } from "@/lib/api";
import {
  initProductAnalytics,
  pathnameToScreen,
  setAnalyticsUserId,
  trackScreenView,
} from "@/lib/analytics";

/** Initializes product analytics once and tracks screen views on route changes. */
export function ProductAnalytics() {
  const pathname = usePathname();

  useEffect(() => {
    initProductAnalytics();
    void getMe()
      .then((me) => setAnalyticsUserId(me.id))
      .catch(() => setAnalyticsUserId(null));
  }, []);

  useEffect(() => {
    if (!pathname?.startsWith("/app")) return;
    trackScreenView(pathnameToScreen(pathname), { props: { path: pathname.slice(0, 128) } });
  }, [pathname]);

  return null;
}
