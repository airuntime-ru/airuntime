"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { getMe } from "@/lib/api";
import {
  initProductAnalytics,
  pathnameToScreen,
  setAnalyticsUserId,
  trackScreenView,
} from "@/lib/analytics";
import { getAnalyticsConsent, hasAnalyticsConsent } from "@/lib/consent";

/** Product analytics only after explicit cookie/analytics consent. */
export function ProductAnalytics() {
  const pathname = usePathname();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    const sync = () => setAllowed(hasAnalyticsConsent());
    sync();
    const onConsent = () => sync();
    window.addEventListener("airuntime:consent", onConsent);
    return () => window.removeEventListener("airuntime:consent", onConsent);
  }, []);

  useEffect(() => {
    if (!allowed) return;
    initProductAnalytics();
    void getMe()
      .then((me) => setAnalyticsUserId(me.id))
      .catch(() => setAnalyticsUserId(null));
  }, [allowed]);

  useEffect(() => {
    if (!allowed || !pathname) return;
    if (getAnalyticsConsent() !== "granted") return;
    trackScreenView(pathnameToScreen(pathname), { props: { path: pathname.slice(0, 128) } });
  }, [allowed, pathname]);

  return null;
}
