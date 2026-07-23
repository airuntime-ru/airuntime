"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/cn";

export function Tabs({
  items,
  sticky = false,
}: {
  items: { href: string; label: string }[];
  sticky?: boolean;
}) {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Разделы проекта"
      className={cn(
        "flex gap-0.5 overflow-x-auto border-b border-[var(--ar-border)] bg-[var(--ar-canvas)] [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        // Sit below the fixed mobile app header (pt-[3.75rem] on main); flush to top on lg.
        sticky &&
          "sticky top-[3.75rem] z-20 -mx-3 px-3 sm:-mx-4 sm:px-4 lg:top-0 lg:-mx-0 lg:px-0"
      )}
    >
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "relative shrink-0 whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35",
              active
                ? "text-[var(--ar-black)] after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full after:bg-[var(--ar-sky)]"
                : "text-[var(--ar-stone)] hover:text-[var(--ar-graphite)]"
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
