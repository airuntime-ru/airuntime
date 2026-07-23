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
    icon: FolderKanban,
    match: (path: string) => path === "/app" || path.startsWith("/app/projects"),
  },
  {
    href: "/app/profile",
    label: "Профиль",
    icon: User,
    match: (path: string) => path === "/app/profile",
  },
];

export function AppSidebar({ credits, onLogout }: { credits: number; onLogout: () => void }) {
  const pathname = usePathname();

  return (
    <aside className="panel-ink fixed inset-y-0 left-0 z-[30] hidden w-60 flex-col border-r border-white/8 lg:flex">
      <div className="flex h-14 items-center px-4">
        <Logo href="/app" variant="full" theme="light" size="sm" />
      </div>

      <nav className="flex-1 space-y-0.5 px-2 py-2">
        {nav.map((item) => {
          const active = item.match(pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              data-tour={item.href === "/app" ? "nav-projects" : undefined}
              className={cn(
                "flex min-h-10 items-center gap-2.5 rounded-[var(--ar-radius-sm)] px-2.5 text-sm font-medium",
                "nav-pill",
                active && "nav-pill-active"
              )}
            >
              <span
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.5rem]",
                  active ? "nav-icon-active" : "bg-white/[0.05] text-white/65"
                )}
              >
                <item.icon size={16} aria-hidden />
              </span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-2 border-t border-white/8 p-3">
        <div className="rounded-[var(--ar-radius-sm)] border border-white/8 bg-white/[0.03] px-3 py-2">
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-white/35">Кредиты</p>
          <p className="mt-0.5 text-sm font-semibold tabular-nums text-white">{credits.toLocaleString("ru-RU")}</p>
        </div>
        <button
          type="button"
          onClick={onLogout}
          className="nav-pill flex min-h-10 w-full items-center gap-2.5 rounded-[var(--ar-radius-sm)] px-2.5 text-left text-sm font-medium"
        >
          <LogOut size={16} aria-hidden />
          Выйти
        </button>
      </div>
    </aside>
  );
}
