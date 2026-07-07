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
    <nav className="glass flex flex-wrap gap-1 rounded-[var(--ar-radius-xl)] p-1">
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link key={item.href} href={item.href} className="relative">
            {active ? (
              <motion.span
                layoutId="project-tab"
                className="absolute inset-0 rounded-[var(--ar-radius-md)] bg-[var(--ar-surface-3)]"
                transition={{ type: "spring", stiffness: 380, damping: 30 }}
              />
            ) : null}
            <span
              className={cn(
                "relative z-10 block rounded-[var(--ar-radius-md)] px-4 py-2 text-sm transition-colors",
                active ? "text-[var(--ar-cloud)]" : "text-[var(--ar-stone)] hover:text-[var(--ar-mist)]"
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
