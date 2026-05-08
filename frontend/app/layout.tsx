/**
 * Root Layout — wird um JEDE Seite herum gerendert.
 *
 * Hier definieren wir:
 *  - HTML-Skelett (<html>, <body>)
 *  - Globale Schriftarten (Geist von Vercel, hochwertig + neutral)
 *  - Default-Metadaten (Browser-Tab-Titel, SEO-Beschreibung)
 *  - Global CSS Import (./globals.css mit Tailwind-Reset)
 *
 * Senior-Pattern: Page-spezifische Metadaten koennen einzelne Pages spaeter
 * via `export const metadata = { ... }` ueberschreiben (z.B. /dashboard:
 * "Dashboard | Kontura AI"). Das passiert automatisch via Next.js-Konvention.
 */

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Kontura AI",
    template: "%s | Kontura AI",
  },
  description:
    "Kontura AI — KI-gestuetzte Buchhaltung fuer den deutschen Mittelstand.",
  // Verhindert, dass die Login-/Dashboard-Pages bei Google indexiert werden.
  // Sobald wir Marketing-Pages haben, koennen wir das pro Page granular
  // erlauben.
  robots: {
    index: false,
    follow: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="de"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}