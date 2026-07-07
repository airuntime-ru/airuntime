import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/cn";

type LogoVariant = "full" | "mark";
type LogoTheme = "light" | "dark";

const heights: Record<"sm" | "md" | "lg", number> = {
  sm: 28,
  md: 36,
  lg: 48,
};

const sources: Record<LogoVariant, Record<LogoTheme, string>> = {
  full: {
    light: "/brand/logo.svg",
    dark: "/brand/logo-dark.svg",
  },
  mark: {
    light: "/brand/logo-mark.svg",
    dark: "/brand/logo-mark.svg",
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
  const width = variant === "mark" ? height : Math.round(height * 0.89);
  const src = sources[variant][theme];

  const image = (
    <Image
      src={src}
      alt="AIRuntime"
      width={width}
      height={height}
      priority={priority}
      className={cn("h-auto w-auto", className)}
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
