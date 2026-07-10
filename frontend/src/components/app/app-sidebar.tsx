"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FolderKanban, LogOut, User } from "lucide-react";

import { Logo } from "@/components/brand/logo";
import { cn } from "@/lib/cn";

const nav = [
  {
    href: "/app",
    label: "Проекты",
    hint: "создать и запустить",
    icon: FolderKanban,
    match: (path: string) => path === "/app" || path.startsWith("/app/projects"),
  },
  {
    href: "/app/profile",
    label: "Профиль",
    hint: "баланс и доступ",
    icon: User,
    match: (path: string) => path === "/app/profile",
  },
];

export function AppSidebar({ credits, onLogout }: { credits: number; onLogout: () => void }) {
  const pathname = usePathname();

  return (
    <aside className="panel-ink fixed left-4 top-4 z-20 hidden h-[calc(100vh-2rem)] w-64 flex-col rounded-[var(--ar-radius-lg)] p-4 lg:flex">
      <div className="relative z-10 mb-7">
        <div className="flex items-center gap-3">
          <Logo href="/app" variant="full" theme="light" size="sm" />
        </div>
        <div className="mt-5 h-px bg-gradient-to-r from-transparent via-white/12 to-transparent" />
        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.22em] text-white/30">
          Рабочее пространство
        </p>
      </div>

      <div className="relative z-10 mb-5 overflow-hidden rounded-[var(--ar-radius-md)] border border-white/10 bg-white/[0.04] p-4">
        <div className="absolute -right-6 -top-6 h-20 w-20 rounded-full bg-[image:var(--ar-accent-gradient)] opacity-20 blur-2xl" aria-hidden />
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/35">Кредиты</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--ar-ink-text-strong)]">
          {credits.toLocaleString()}
        </p>
      </div>

      <nav className="relative z-10 flex-1 space-y-1.5">
        {nav.map((item) => {
          const active = item.match(pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              data-tour={item.href === "/app" ? "nav-projects" : undefined}
              className={cn(
                "group flex items-center gap-3 rounded-[var(--ar-radius-sm)] px-3 py-3",
                "nav-pill",
                active && "nav-pill-active"
              )}
            >
              <span
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-[calc(var(--ar-radius-sm)-2px)] transition-colors",
                  active ? "nav-icon-active text-white" : "bg-white/[0.06] text-white/70"
                )}
              >
                <item.icon size={17} />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold">{item.label}</span>
                <span className="block truncate text-xs text-white/30">{item.hint}</span>
              </span>
            </Link>
          );
        })}
      </nav>

      <button
        type="button"
        onClick={onLogout}
        className="nav-pill relative z-10 mt-4 flex items-center gap-3 rounded-[var(--ar-radius-sm)] px-3 py-2.5 text-left text-sm font-medium"
      >
        <LogOut size={17} />
        Выйти
      </button>
    </aside>
  );
}
