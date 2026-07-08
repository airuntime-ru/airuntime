"use client";

import { motion } from "framer-motion";
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
    <nav className="flex gap-1 overflow-x-auto rounded-[var(--ar-radius-sm)] border border-black/10 bg-white p-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link key={item.href} href={item.href} className="relative shrink-0">
            {active ? (
              <motion.span
                layoutId="project-tab"
                className="absolute inset-0 rounded-[var(--ar-radius-sm)] bg-black/5"
                transition={{ type: "spring", stiffness: 380, damping: 30 }}
              />
            ) : null}
            <span
              className={cn(
                "relative z-10 block whitespace-nowrap rounded-[var(--ar-radius-sm)] px-3 py-2 text-sm font-semibold transition-colors sm:px-4",
                active ? "text-[var(--ar-black)]" : "text-[var(--ar-stone)] hover:text-[var(--ar-black)]"
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
