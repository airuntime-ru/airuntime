"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, FolderKanban, Gauge, Settings, User } from "lucide-react";

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
    <aside className="glass fixed left-4 top-4 z-20 hidden h-[calc(100vh-2rem)] w-64 flex-col rounded-[var(--ar-radius-xl)] p-4 lg:flex">
      <div className="mb-6">
        <Logo href="/app" variant="full" theme="dark" size="sm" />
        <p className="mt-2 text-lg font-semibold text-[var(--ar-cloud)]">Рабочая область</p>
      </div>
      <div className="mb-5 rounded-[var(--ar-radius-lg)] border border-white/10 bg-white/5 p-3">
        <p className="text-xs uppercase tracking-wide text-[var(--ar-stone)]">Кредиты</p>
        <p className="mt-1 text-xl font-semibold tabular-nums text-[var(--ar-cloud)]">
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
              className={cn(
                "flex items-center gap-2 rounded-[var(--ar-radius-md)] px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-white/12 text-[var(--ar-cloud)]"
                  : "text-[var(--ar-mist)] hover:bg-white/8 hover:text-[var(--ar-cloud)]"
              )}
            >
              <item.icon size={16} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <button
        type="button"
        onClick={onLogout}
        className="mt-4 rounded-[var(--ar-radius-md)] px-3 py-2 text-left text-sm text-[var(--ar-mist)] hover:bg-white/8 hover:text-[var(--ar-cloud)]"
      >
        Выйти
      </button>
    </aside>
  );
}
