"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FolderKanban, LogOut, Menu, User, X } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { Logo } from "@/components/brand/logo";
import { cn } from "@/lib/cn";

const primaryNav = [
  {
    href: "/app",
    label: "Проекты",
    icon: FolderKanban,
    match: (path: string) => path === "/app" || path.startsWith("/app/projects"),
  },
  { href: "/app/profile", label: "Профиль", icon: User, match: (path: string) => path === "/app/profile" },
];

export function AppMobileHeader({ credits }: { credits: number }) {
  return (
    <header className="fixed inset-x-0 top-0 z-[30] border-b border-white/10 bg-[var(--ar-ink)] px-4 py-2.5 lg:hidden">
      <div className="flex min-h-10 items-center justify-between gap-3">
        <Logo href="/app" variant="mark" theme="light" size="sm" />
        <p className="rounded-[0.5rem] border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-white/55">
          <span className="text-white/35">Кредиты </span>
          <span className="font-semibold tabular-nums text-white">{credits.toLocaleString("ru-RU")}</span>
        </p>
      </div>
    </header>
  );
}

export function AppMobileNav({ credits, onLogout }: { credits: number; onLogout: () => void }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuId = useId();

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  return (
    <>
      <nav className="fixed inset-x-0 bottom-0 z-[30] border-t border-white/10 bg-[var(--ar-ink)] px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 lg:hidden">
        <div className="mx-auto flex max-w-lg items-center justify-around gap-1">
          {primaryNav.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                data-tour={item.href === "/app" ? "nav-projects" : undefined}
                className={cn(
                  "flex min-h-11 min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-[var(--ar-radius-sm)] px-2 text-[0.68rem] font-semibold transition-colors",
                  active ? "nav-pill-active" : "text-white/40"
                )}
              >
                <item.icon size={18} aria-hidden />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-expanded={menuOpen}
            aria-controls={menuId}
            className="flex min-h-11 min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-[var(--ar-radius-sm)] px-2 text-[0.68rem] font-semibold text-white/40"
          >
            <Menu size={18} aria-hidden />
            <span>Ещё</span>
          </button>
        </div>
      </nav>

      {menuOpen ? (
        <div className="fixed inset-0 z-[40] lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            aria-label="Закрыть меню"
            onClick={() => setMenuOpen(false)}
          />
          <div
            id={menuId}
            className="panel-ink absolute inset-x-0 bottom-0 rounded-t-[var(--ar-radius-lg)] p-4 pb-[max(1rem,env(safe-area-inset-bottom))]"
            role="dialog"
            aria-modal="true"
            aria-label="Меню"
          >
            <div className="mb-4 flex items-center justify-between">
              <p className="text-sm font-semibold text-white">Меню</p>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--ar-radius-sm)] text-white/50 hover:bg-white/[0.06]"
                aria-label="Закрыть"
              >
                <X size={18} aria-hidden />
              </button>
            </div>
            <div className="mb-3 rounded-[var(--ar-radius-sm)] border border-white/10 bg-white/[0.03] px-3 py-2">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-white/35">Кредиты</p>
              <p className="mt-0.5 text-sm font-semibold tabular-nums text-white">
                {credits.toLocaleString("ru-RU")}
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                onLogout();
              }}
              className="nav-pill flex min-h-11 w-full items-center gap-3 rounded-[var(--ar-radius-sm)] px-3 text-left text-sm font-medium"
            >
              <LogOut size={18} aria-hidden />
              Выйти
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
