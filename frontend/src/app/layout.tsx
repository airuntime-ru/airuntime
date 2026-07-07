import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "cyrillic"],
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
  description: "Опишите идею. AIRuntime соберет и запустит проект.",
  metadataBase: new URL(siteUrl),
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "48x48", type: "image/x-icon" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
    shortcut: "/favicon.ico",
  },
  manifest: "/site.webmanifest",
  openGraph: {
    title: "AIRuntime",
    description: "Опишите идею. AIRuntime соберет и запустит проект.",
    url: siteUrl,
    siteName: "AIRuntime",
    type: "website",
    images: [
      {
        url: "/brand/logo-full.png",
        width: 1024,
        height: 1024,
        alt: "AIRuntime",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AIRuntime",
    description: "Опишите идею. AIRuntime соберет и запустит проект.",
    images: ["/brand/logo-full.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className={`${inter.variable} ${jetbrains.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-[var(--background)] text-[var(--foreground)]">{children}</body>
    </html>
  );
}
