import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { LOGIN_HREF, navItems } from "@/lib/landing/content";

export function SiteFooter() {
  return (
    <footer className="border-t border-black/[0.07] bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-5 py-10 sm:px-8 sm:py-12 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <Logo href="/" variant="full" theme="dark" size="sm" />
          <p className="mt-3 max-w-sm text-sm text-[var(--ar-mist)]">
            Опишите идею. Получите работающий сайт или Telegram-бота.
          </p>
        </div>
        <nav aria-label="Навигация в подвале" className="flex flex-wrap gap-x-5 gap-y-2">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-sm text-[var(--ar-graphite)] transition-colors hover:text-[var(--ar-black)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35"
            >
              {item.label}
            </a>
          ))}
          <Link
            href={LOGIN_HREF}
            className="text-sm font-medium text-[var(--ar-sky)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35"
          >
            Войти
          </Link>
        </nav>
      </div>
      <div className="border-t border-black/[0.06]">
        <p className="mx-auto max-w-6xl px-5 py-5 text-xs text-[var(--ar-stone)] sm:px-8">
          © {new Date().getFullYear()} AIRuntime
        </p>
      </div>
    </footer>
  );
}
