export const tokens = {
  color: {
    white: "var(--ar-white)",
    cloud: "var(--ar-cloud)",
    mist: "var(--ar-mist)",
    stone: "var(--ar-stone)",
    graphite: "var(--ar-graphite)",
    black: "var(--ar-black)",
    sky: "var(--ar-sky)",
    cyan: "var(--ar-cyan)",
    indigo: "var(--ar-indigo)",
    purple: "var(--ar-purple)",
  },
  radius: {
    sm: "var(--ar-radius-sm)",
    md: "var(--ar-radius-md)",
    lg: "var(--ar-radius-lg)",
    xl: "var(--ar-radius-xl)",
  },
  spacing: {
    xs: "var(--ar-space-xs)",
    sm: "var(--ar-space-sm)",
    md: "var(--ar-space-md)",
    lg: "var(--ar-space-lg)",
    xl: "var(--ar-space-xl)",
  },
  motion: {
    spring: { type: "spring" as const, stiffness: 260, damping: 28 },
    ease: { duration: 0.45, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] },
  },
} as const;
