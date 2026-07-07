"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, FolderKanban, Gauge, LogOut, Settings, User } from "lucide-react";

import { Logo } from "@/components/brand/logo";
import { cn } from "@/lib/cn";

const nav = [
  { href: "/app", label: "Обзор", icon: Gauge },
  { href: "/app/projects", label: "Проекты", icon: FolderKanban },
  { href: "/app/chat", label: "Чат", icon: Bot },
  { href: "/app/profile", label: "Профиль", icon: User },
  { href: "/app/settings", label: "Настройки", icon: Settings },
];

export function AppSidebar({ credits, onLogout }: { credits: number; onLogout: () => void }) {
  const pathname = usePathname();

  return (
    <aside className="glass fixed left-4 top-4 z-20 hidden h-[calc(100vh-2rem)] w-64 flex-col rounded-[var(--ar-radius-sm)] p-4 lg:flex">
      <div className="mb-7">
        <Logo href="/app" variant="full" theme="dark" size="sm" />
        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.22em] text-[var(--ar-stone)]">
          Рабочая область
        </p>
      </div>
      <div className="mb-5 rounded-[var(--ar-radius-sm)] border border-[var(--ar-border)] bg-white/70 p-4 shadow-sm shadow-sky-950/5">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--ar-stone)]">Кредиты</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--ar-black)]">
          {credits.toLocaleString()}
        </p>
      </div>
      <nav className="flex-1 space-y-1">
        {nav.map((item) => {
          const active = pathname === item.href || (item.href !== "/app" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              data-tour={item.href === "/app/projects" ? "nav-projects" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-[var(--ar-radius-sm)] px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-white text-[var(--ar-sky)] shadow-sm shadow-sky-950/5"
                  : "text-[var(--ar-mist)] hover:bg-white/70 hover:text-[var(--ar-black)]"
              )}
            >
              <item.icon size={17} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <button
        type="button"
        onClick={onLogout}
        className="mt-4 flex items-center gap-3 rounded-[var(--ar-radius-sm)] px-3 py-2.5 text-left text-sm font-medium text-[var(--ar-mist)] hover:bg-white/70 hover:text-[var(--ar-black)]"
      >
        <LogOut size={17} />
        Выйти
      </button>
    </aside>
  );
}
