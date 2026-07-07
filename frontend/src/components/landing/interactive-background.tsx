"use client";

import { motion, useMotionTemplate, useMotionValue } from "framer-motion";

export function InteractiveBackground() {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const glow = useMotionTemplate`radial-gradient(520px circle at ${mouseX}px ${mouseY}px, rgba(35,136,255,0.13), transparent 62%)`;

  return (
    <div className="fixed inset-0 z-0 overflow-hidden atmosphere" aria-hidden>
      <div className="absolute inset-0 atmosphere-grid" />
      <div
        className="absolute inset-0 max-sm:hidden"
        onMouseMove={(event) => {
          mouseX.set(event.clientX);
          mouseY.set(event.clientY);
        }}
      >
        <motion.div className="pointer-events-none absolute inset-0" style={{ background: glow }} />
      </div>
      <motion.div
        className="pointer-events-none absolute inset-x-[-12%] top-[10%] h-48 rotate-[-4deg] bg-[linear-gradient(90deg,transparent,rgba(35,136,255,0.12),rgba(24,199,202,0.12),transparent)] blur-xl"
        animate={{ x: ["-4%", "4%", "-4%"], opacity: [0.5, 0.9, 0.5] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="pointer-events-none absolute inset-x-[-12%] bottom-[12%] h-40 rotate-[3deg] bg-[linear-gradient(90deg,transparent,rgba(110,231,183,0.12),rgba(255,138,122,0.09),transparent)] blur-xl"
        animate={{ x: ["5%", "-5%", "5%"], opacity: [0.35, 0.72, 0.35] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
