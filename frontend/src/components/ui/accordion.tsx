"use client";

import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/cn";

type Item = { question: string; answer: string };

type AccordionProps = {
  items: Item[];
  onOpenChange?: (index: number | null) => void;
};

export function Accordion({ items, onOpenChange }: AccordionProps) {
  const [open, setOpen] = useState<number | null>(0);
  const reduceMotion = useReducedMotion();
  const baseId = useId();

  const toggle = (index: number) => {
    const next = open === index ? null : index;
    setOpen(next);
    onOpenChange?.(next);
  };

  return (
    <div className="space-y-2">
      {items.map((item, index) => {
        const isOpen = open === index;
        const panelId = `${baseId}-panel-${index}`;
        const buttonId = `${baseId}-button-${index}`;

        return (
          <div
            key={item.question}
            className="overflow-hidden rounded-[0.75rem] border border-black/[0.08] bg-white"
          >
            <h3>
              <button
                id={buttonId}
                type="button"
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--ar-sky)]/35"
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => toggle(index)}
              >
                <span className="font-medium text-[var(--ar-black)]">{item.question}</span>
                <ChevronDown
                  size={16}
                  aria-hidden
                  className={cn(
                    "shrink-0 text-[var(--ar-stone)] transition-transform",
                    isOpen && "rotate-180"
                  )}
                />
              </button>
            </h3>
            <AnimatePresence initial={false}>
              {isOpen ? (
                <motion.div
                  id={panelId}
                  role="region"
                  aria-labelledby={buttonId}
                  initial={reduceMotion ? false : { height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={reduceMotion ? undefined : { height: 0, opacity: 0 }}
                  transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
                  className="overflow-hidden"
                >
                  <p className="px-5 pb-4 text-sm leading-relaxed text-[var(--ar-mist)]">
                    {item.answer}
                  </p>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
