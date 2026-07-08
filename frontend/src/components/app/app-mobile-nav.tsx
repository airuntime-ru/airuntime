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

export function AppMobileHeader({ credits }: { credits: number }) {
  return (
    <header className="fixed inset-x-0 top-0 z-30 border-b border-black/10 bg-white/90 px-4 py-3 shadow-sm backdrop-blur-2xl lg:hidden">
      <div className="flex items-center justify-between gap-3">
        <Logo href="/app" variant="mark" theme="dark" size="sm" />
        <div className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-[var(--ar-mist)]">
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
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-black/10 bg-white/92 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-12px_36px_rgba(7,20,38,0.08)] backdrop-blur-2xl lg:hidden">
        <div className="mx-auto flex max-w-lg items-center justify-around gap-1">
          {primaryNav.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                data-tour={item.href === "/app" ? "nav-projects" : undefined}
                className={cn(
                  "flex min-w-0 flex-1 flex-col items-center gap-1 rounded-[var(--ar-radius-sm)] px-2 py-2 text-[0.68rem] font-semibold",
                  active ? "bg-black/5 text-[var(--ar-black)] shadow-sm" : "text-[var(--ar-stone)]"
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
            className="flex min-w-0 flex-1 flex-col items-center gap-1 rounded-[var(--ar-radius-sm)] px-2 py-2 text-[0.68rem] font-semibold text-[var(--ar-stone)]"
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
            className="absolute inset-0 bg-[#071426]/24 backdrop-blur-md"
            aria-label="Закрыть меню"
            onClick={() => setMenuOpen(false)}
          />
          <div className="absolute inset-x-0 bottom-0 rounded-t-[var(--ar-radius-sm)] border border-black/10 bg-white p-4 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-[0_-12px_40px_rgba(7,20,38,0.1)]">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-sm font-semibold text-[var(--ar-black)]">Меню</p>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                className="rounded-[var(--ar-radius-sm)] p-2 text-[var(--ar-stone)] hover:bg-black/5"
                aria-label="Закрыть"
              >
                <X size={18} />
              </button>
            </div>
            <div className="mb-4 rounded-[var(--ar-radius-sm)] border border-black/10 bg-white p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--ar-stone)]">Кредиты</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--ar-black)]">
                {credits.toLocaleString()}
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                onLogout();
              }}
              className="flex w-full items-center gap-3 rounded-[var(--ar-radius-sm)] px-3 py-3 text-left text-sm font-medium text-[var(--ar-mist)] hover:bg-black/5"
            >
              <LogOut size={18} />
              Выйти
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
