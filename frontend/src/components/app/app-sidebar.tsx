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
    <aside className="fixed left-4 top-4 z-20 hidden h-[calc(100vh-2rem)] w-64 flex-col rounded-[var(--ar-radius-sm)] border border-black/10 bg-white/85 p-4 shadow-[0_16px_52px_rgba(7,20,38,0.08)] backdrop-blur-xl lg:flex">
      <div className="mb-7">
        <div className="flex items-center gap-3">
          <Logo href="/app" variant="full" theme="dark" size="sm" />
        </div>
        <div className="mt-5 h-px bg-black/10" />
        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.22em] text-[var(--ar-stone)]">
          Рабочее пространство
        </p>
      </div>

      <div className="mb-5 rounded-[var(--ar-radius-sm)] border border-black/10 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--ar-stone)]">Кредиты</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--ar-black)]">
          {credits.toLocaleString()}
        </p>
      </div>

      <nav className="flex-1 space-y-2">
        {nav.map((item) => {
          const active = item.match(pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              data-tour={item.href === "/app" ? "nav-projects" : undefined}
              className={cn(
                "group flex items-center gap-3 rounded-[var(--ar-radius-sm)] border px-3 py-3 transition-all",
                active
                  ? "border-black/10 bg-white text-[var(--ar-black)] shadow-sm"
                  : "border-transparent text-[var(--ar-mist)] hover:border-black/10 hover:bg-white/70 hover:text-[var(--ar-black)]"
              )}
            >
              <span
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--ar-radius-sm)] transition-colors",
                  active ? "bg-[var(--ar-black)] text-white" : "bg-black/5 text-[var(--ar-black)]"
                )}
              >
                <item.icon size={17} />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold">{item.label}</span>
                <span className="block truncate text-xs text-[var(--ar-stone)]">{item.hint}</span>
              </span>
            </Link>
          );
        })}
      </nav>

      <button
        type="button"
        onClick={onLogout}
        className="mt-4 flex items-center gap-3 rounded-[var(--ar-radius-sm)] px-3 py-2.5 text-left text-sm font-medium text-[var(--ar-mist)] hover:bg-white/60 hover:text-[var(--ar-black)]"
      >
        <LogOut size={17} />
        Выйти
      </button>
    </aside>
  );
}
