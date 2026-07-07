"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, FolderKanban, Gauge, Menu, Settings, User, X } from "lucide-react";
import { useState } from "react";

import { Logo } from "@/components/brand/logo";
import { cn } from "@/lib/cn";

const primaryNav = [
  { href: "/app", label: "Обзор", icon: Gauge, match: (path: string) => path === "/app" },
  {
    href: "/app/projects",
    label: "Проекты",
    icon: FolderKanban,
    match: (path: string) => path.startsWith("/app/projects"),
  },
  { href: "/app/chat", label: "Чат", icon: Bot, match: (path: string) => path === "/app/chat" },
];

const menuNav = [
  { href: "/app/profile", label: "Профиль", icon: User },
  { href: "/app/settings", label: "Настройки", icon: Settings },
];

export function AppMobileHeader({ credits }: { credits: number }) {
  return (
    <header className="fixed inset-x-0 top-0 z-30 border-b border-white/10 bg-[var(--ar-black)]/80 px-4 py-3 backdrop-blur-md lg:hidden">
      <div className="flex items-center justify-between gap-3">
        <Logo href="/app" variant="mark" theme="dark" size="sm" />
        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-[var(--ar-mist)]">
          <span className="text-[var(--ar-stone)]">Кредиты </span>
          <span className="font-semibold tabular-nums text-[var(--ar-cloud)]">{credits.toLocaleString()}</span>
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
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-[var(--ar-black)]/90 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-md lg:hidden">
        <div className="mx-auto flex max-w-lg items-center justify-around gap-1">
          {primaryNav.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex min-w-0 flex-1 flex-col items-center gap-1 rounded-[var(--ar-radius-md)] px-2 py-2 text-[0.65rem]",
                  active ? "text-[var(--ar-sky)]" : "text-[var(--ar-stone)]"
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
            className="flex min-w-0 flex-1 flex-col items-center gap-1 rounded-[var(--ar-radius-md)] px-2 py-2 text-[0.65rem] text-[var(--ar-stone)]"
          >
            <Menu size={18} />
            <span>Ещё</span>
          </button>
        </div>
      </nav>

      {menuOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/60"
            aria-label="Закрыть меню"
            onClick={() => setMenuOpen(false)}
          />
          <div className="absolute inset-x-0 bottom-0 rounded-t-[var(--ar-radius-xl)] border border-white/10 bg-[var(--ar-graphite)] p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-sm font-medium text-[var(--ar-cloud)]">Меню</p>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                className="rounded-[var(--ar-radius-md)] p-2 text-[var(--ar-stone)] hover:bg-white/8"
                aria-label="Закрыть"
              >
                <X size={18} />
              </button>
            </div>
            <div className="mb-4 rounded-[var(--ar-radius-lg)] border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-wide text-[var(--ar-stone)]">Кредиты</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--ar-cloud)]">
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
                      "flex items-center gap-3 rounded-[var(--ar-radius-md)] px-3 py-3 text-sm",
                      active
                        ? "bg-white/12 text-[var(--ar-cloud)]"
                        : "text-[var(--ar-mist)] hover:bg-white/8"
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
                className="flex w-full items-center gap-3 rounded-[var(--ar-radius-md)] px-3 py-3 text-left text-sm text-[var(--ar-mist)] hover:bg-white/8"
              >
                Выйти
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
