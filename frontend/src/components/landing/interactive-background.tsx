"use client";

import { motion, useMotionTemplate, useMotionValue } from "framer-motion";

const clouds = [
  { width: 280, top: "12%", left: "-8%", delay: 0, duration: 28 },
  { width: 220, top: "34%", left: "72%", delay: 4, duration: 32 },
  { width: 320, top: "58%", left: "18%", delay: 2, duration: 36 },
  { width: 180, top: "78%", left: "64%", delay: 6, duration: 30 },
];

const mobileClouds = [
  { width: 160, top: "8%", left: "-12%", delay: 0, duration: 28 },
  { width: 140, top: "42%", left: "68%", delay: 3, duration: 32 },
  { width: 180, top: "72%", left: "10%", delay: 1, duration: 36 },
];

export function InteractiveBackground() {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const glow = useMotionTemplate`radial-gradient(420px circle at ${mouseX}px ${mouseY}px, rgba(94,184,255,0.16), transparent 65%)`;

  return (
    <div className="fixed inset-0 atmosphere overflow-hidden" aria-hidden>
      <div
        className="absolute inset-0 max-sm:hidden"
        onMouseMove={(event) => {
          mouseX.set(event.clientX);
          mouseY.set(event.clientY);
        }}
      >
        <motion.div className="pointer-events-none absolute inset-0" style={{ background: glow }} />
      </div>

      <div className="sm:hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_45%_at_50%_0%,rgba(94,184,255,0.14),transparent)]" />
      </div>

      {clouds.map((cloud, index) => (
        <motion.div
          key={`desktop-${index}`}
          className="cloud-blob pointer-events-none absolute hidden sm:block"
          style={{ width: cloud.width, top: cloud.top, left: cloud.left }}
          animate={{ x: [0, 42, -24, 0], y: [0, -18, 12, 0], opacity: [0.35, 0.55, 0.4, 0.35] }}
          transition={{ duration: cloud.duration, repeat: Infinity, ease: "easeInOut", delay: cloud.delay }}
        />
      ))}

      {mobileClouds.map((cloud, index) => (
        <motion.div
          key={`mobile-${index}`}
          className="cloud-blob pointer-events-none absolute sm:hidden"
          style={{ width: cloud.width, top: cloud.top, left: cloud.left }}
          animate={{ x: [0, 20, -12, 0], y: [0, -10, 8, 0], opacity: [0.25, 0.4, 0.3, 0.25] }}
          transition={{ duration: cloud.duration, repeat: Infinity, ease: "easeInOut", delay: cloud.delay }}
        />
      ))}

      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,transparent_0%,var(--ar-black)_88%)]" />
    </div>
  );
}
