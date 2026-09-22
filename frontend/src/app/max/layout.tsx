import type { Metadata } from "next";
import Script from "next/script";

import "./max.css";

export const metadata: Metadata = {
  title: "AIRuntime для MAX",
  description: "AIRuntime и заявки прямо в мессенджере MAX.",
  // A mini app is opened from inside MAX, never found in search.
  robots: { index: false, follow: false },
};

export default function MaxLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="max-app">
      {/* beforeInteractive so window.WebApp exists before the first client render tries to
          read initData - otherwise every load would flash the "open inside MAX" state. */}
      <Script src="https://st.max.ru/js/max-web-app.js" strategy="beforeInteractive" />
      {children}
    </div>
  );
}
