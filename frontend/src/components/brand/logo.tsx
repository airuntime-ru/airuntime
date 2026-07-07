import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/cn";

type LogoVariant = "full" | "mark" | "stacked";
type LogoTheme = "light" | "dark";

const heights: Record<"sm" | "md" | "lg", number> = {
  sm: 28,
  md: 36,
  lg: 48,
};

const aspect: Record<LogoVariant, number> = {
  mark: 1,
  full: 5.05,
  stacked: 1,
};

const sources: Record<LogoVariant, Record<LogoTheme, string>> = {
  full: {
    light: "/brand/logo-wordmark.png",
    dark: "/brand/logo-wordmark.png",
  },
  mark: {
    light: "/brand/logo-mark.png",
    dark: "/brand/logo-mark.png",
  },
  stacked: {
    light: "/brand/logo-full.png",
    dark: "/brand/logo-full.png",
  },
};

type LogoProps = {
  variant?: LogoVariant;
  theme?: LogoTheme;
  size?: keyof typeof heights;
  className?: string;
  href?: string;
  priority?: boolean;
};

export function Logo({
  variant = "full",
  theme = "dark",
  size = "md",
  className,
  href,
  priority = false,
}: LogoProps) {
  const height = heights[size];
  const width = Math.round(height * aspect[variant]);
  const src = sources[variant][theme];

  const image = (
    <Image
      src={src}
      alt="AIRuntime"
      width={width}
      height={height}
      priority={priority}
      className={cn("h-auto w-auto object-contain", className)}
      style={{ height, width: "auto", maxWidth: width }}
    />
  );

  if (href) {
    return (
      <Link href={href} className="inline-flex shrink-0 items-center">
        {image}
      </Link>
    );
  }

  return image;
}
