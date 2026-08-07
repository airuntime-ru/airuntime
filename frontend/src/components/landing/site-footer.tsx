import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { LOGIN_HREF, navItems } from "@/lib/landing/content";

export function SiteFooter() {
  return (
    <footer className="border-t border-white/8 bg-[#05070f] text-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-5 py-12 sm:px-8 sm:py-14 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <Logo href="/" variant="full" theme="light" size="sm" />
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/55">
            Опишите идею. Получите работающий сайт или Telegram-бота.
          </p>
        </div>
        <nav aria-label="Навигация в подвале" className="flex flex-wrap gap-x-6 gap-y-3">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-sm text-white/55 transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
            >
              {item.label}
            </a>
          ))}
          <Link
            href={LOGIN_HREF}
            className="text-sm font-medium text-[#8ec4ff] transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
          >
            Войти
          </Link>
        </nav>
      </div>
      <div className="border-t border-white/[0.06]">
        <p className="mx-auto max-w-6xl px-5 py-6 text-xs text-white/45 sm:px-8">
          © {new Date().getFullYear()} AIRuntime
        </p>
      </div>
    </footer>
  );
}
