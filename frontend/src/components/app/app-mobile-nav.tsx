"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FolderKanban, LogOut, Menu, User, X } from "lucide-react";
import { useState } from "react";

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

const menuNav: { href: string; label: string; icon: typeof User }[] = [];

export function AppMobileHeader({ credits }: { credits: number }) {
  return (
    <header className="fixed inset-x-0 top-0 z-30 border-b border-[var(--ar-border)] bg-white/90 px-4 py-3 backdrop-blur-xl lg:hidden">
      <div className="flex items-center justify-between gap-3">
        <Logo href="/app" variant="mark" theme="dark" size="sm" />
        <div className="rounded-full border border-[var(--ar-border)] bg-white/80 px-3 py-1 text-xs text-[var(--ar-mist)] shadow-sm shadow-sky-950/5">
          <span className="text-[var(--ar-stone)]">Кредиты </span>
          <span className="font-semibold tabular-nums text-[var(--ar-black)]">{credits.toLocaleString()}</span>
        </div>
      </div>
    </header>
  );
}

export function AppMobileNav({ credits, onLogout }: { credits: number; onLogout: () => void }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <>
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-[var(--ar-border)] bg-white/90 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-14px_50px_rgba(56,112,180,0.12)] backdrop-blur-xl lg:hidden">
        <div className="mx-auto flex max-w-lg items-center justify-around gap-1">
          {primaryNav.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                data-tour={item.href === "/app" ? "nav-projects" : undefined}
                className={cn(
                  "flex min-w-0 flex-1 flex-col items-center gap-1 rounded-[var(--ar-radius-sm)] px-2 py-2 text-[0.68rem] font-medium",
                  active ? "bg-sky-50 text-[var(--ar-sky)]" : "text-[var(--ar-stone)]"
                )}
              >
                <item.icon size={18} />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            className="flex min-w-0 flex-1 flex-col items-center gap-1 rounded-[var(--ar-radius-sm)] px-2 py-2 text-[0.68rem] font-medium text-[var(--ar-stone)]"
          >
            <Menu size={18} />
            <span>Еще</span>
          </button>
        </div>
      </nav>

      {menuOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/30 backdrop-blur-sm"
            aria-label="Закрыть меню"
            onClick={() => setMenuOpen(false)}
          />
          <div className="absolute inset-x-0 bottom-0 rounded-t-[var(--ar-radius-xl)] border border-[var(--ar-border)] bg-white p-4 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-[0_-24px_80px_rgba(56,112,180,0.18)]">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-sm font-semibold text-[var(--ar-black)]">Меню</p>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                className="rounded-[var(--ar-radius-sm)] p-2 text-[var(--ar-stone)] hover:bg-sky-50"
                aria-label="Закрыть"
              >
                <X size={18} />
              </button>
            </div>
            <div className="mb-4 rounded-[var(--ar-radius-sm)] border border-[var(--ar-border)] bg-sky-50/70 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--ar-stone)]">Кредиты</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--ar-black)]">
                {credits.toLocaleString()}
              </p>
            </div>
            <div className="space-y-1">
              {menuNav.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-[var(--ar-radius-sm)] px-3 py-3 text-sm font-medium",
                      active ? "bg-sky-50 text-[var(--ar-sky)]" : "text-[var(--ar-mist)] hover:bg-sky-50"
                    )}
                  >
                    <item.icon size={18} />
                    {item.label}
                  </Link>
                );
              })}
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onLogout();
                }}
                className="flex w-full items-center gap-3 rounded-[var(--ar-radius-sm)] px-3 py-3 text-left text-sm font-medium text-[var(--ar-mist)] hover:bg-sky-50"
              >
                <LogOut size={18} />
                Выйти
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
