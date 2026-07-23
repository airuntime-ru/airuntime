"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { Menu, X } from "lucide-react";

import { Logo } from "@/components/brand/logo";
import { LOGIN_HREF, navItems } from "@/lib/landing/content";
import { cn } from "@/lib/cn";

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const menuId = useId();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <header
      className={cn(
        "sticky top-0 z-40 border-b transition-[background-color,box-shadow,border-color] duration-200",
        scrolled
          ? "border-black/[0.08] bg-white/90 shadow-[0_8px_30px_rgba(7,20,38,0.06)] backdrop-blur-md"
          : "border-transparent bg-[#f7f8fa]/92 backdrop-blur-sm"
      )}
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-5 sm:h-16 sm:px-8">
        <Logo href="/" variant="full" theme="dark" size="sm" priority />

        <nav className="hidden items-center gap-1 lg:flex" aria-label="Основная навигация">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-[0.5rem] px-3 py-2 text-sm font-medium text-[var(--ar-graphite)] transition-colors hover:bg-black/[0.04] hover:text-[var(--ar-black)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <Link
            href={LOGIN_HREF}
            className="hidden rounded-[0.5rem] px-3 py-2 text-sm font-medium text-[var(--ar-graphite)] transition-colors hover:text-[var(--ar-black)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35 sm:inline-flex"
          >
            Войти
          </Link>
          <Link
            href={LOGIN_HREF}
            className="inline-flex h-9 items-center justify-center rounded-[0.55rem] bg-[var(--ar-black)] px-3.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/40 sm:h-10 sm:px-4"
          >
            Создать проект
          </Link>
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-[0.55rem] border border-black/10 bg-white text-[var(--ar-black)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35 lg:hidden"
            aria-expanded={open}
            aria-controls={menuId}
            aria-label={open ? "Закрыть меню" : "Открыть меню"}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X size={18} aria-hidden /> : <Menu size={18} aria-hidden />}
          </button>
        </div>
      </div>

      {open ? (
        <div id={menuId} className="border-t border-black/[0.06] bg-white lg:hidden">
          <nav
            className="mx-auto flex max-w-6xl flex-col gap-1 px-5 py-4 sm:px-8"
            aria-label="Мобильная навигация"
          >
            {navItems.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="rounded-[0.55rem] px-3 py-3 text-base font-medium text-[var(--ar-black)] hover:bg-black/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35"
                onClick={() => setOpen(false)}
              >
                {item.label}
              </a>
            ))}
            <Link
              href={LOGIN_HREF}
              className="rounded-[0.55rem] px-3 py-3 text-base font-medium text-[var(--ar-sky)] hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35"
              onClick={() => setOpen(false)}
            >
              Войти
            </Link>
          </nav>
        </div>
      ) : null}
    </header>
  );
}
