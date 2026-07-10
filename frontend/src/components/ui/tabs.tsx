"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/cn";

export function Tabs({
  items,
}: {
  items: { href: string; label: string }[];
}) {
  const pathname = usePathname();

  return (
    <nav className="flex gap-1 overflow-x-auto rounded-[var(--ar-radius-sm)] border border-black/[0.07] bg-white p-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link key={item.href} href={item.href} className="relative shrink-0">
            <span
              className={cn(
                "relative z-10 block whitespace-nowrap rounded-[calc(var(--ar-radius-sm)-2px)] px-3 py-2 text-sm font-semibold transition-all duration-200 sm:px-4",
                active
                  ? "bg-[var(--ar-accent-gradient-soft)] text-[var(--ar-black)] shadow-[inset_0_0_0_1px_rgba(35,136,255,0.18)]"
                  : "text-[var(--ar-stone)] hover:bg-black/[0.03] hover:text-[var(--ar-black)]"
              )}
            >
              {item.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
