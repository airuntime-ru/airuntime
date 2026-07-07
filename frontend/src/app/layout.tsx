import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
});

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? process.env.FRONTEND_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  title: {
    default: "AIRuntime",
    template: "%s · AIRuntime",
  },
  description: "Опишите. Мы воплотим.",
  metadataBase: new URL(siteUrl),
  icons: {
    icon: [
      { url: "/icon.svg", type: "image/svg+xml" },
      { url: "/brand/logo-mark.svg", type: "image/svg+xml" },
    ],
    apple: "/brand/logo-mark.svg",
    shortcut: "/icon.svg",
  },
  manifest: "/site.webmanifest",
  openGraph: {
    title: "AIRuntime",
    description: "Опишите. Мы воплотим.",
    url: siteUrl,
    siteName: "AIRuntime",
    type: "website",
    images: [
      {
        url: "/brand/logo-dark.svg",
        width: 480,
        height: 220,
        alt: "AIRuntime",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AIRuntime",
    description: "Опишите. Мы воплотим.",
    images: ["/brand/logo-dark.svg"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className={`${inter.variable} ${jetbrains.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-[var(--ar-black)] text-[var(--ar-cloud)]">{children}</body>
    </html>
  );
}
