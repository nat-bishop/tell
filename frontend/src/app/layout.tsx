import type { Metadata } from "next";
import { Cormorant, Cormorant_SC, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const cormorant = Cormorant({
  variable: "--font-literary",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const cormorantSC = Cormorant_SC({
  variable: "--font-literary-sc",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-system",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  title: "tell",
  description: "a game of words and suspicion",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${cormorant.variable} ${cormorantSC.variable} ${ibmPlexMono.variable}`}
        style={{ backgroundColor: 'var(--page)', color: 'var(--ink)' }}
      >
        {children}
      </body>
    </html>
  );
}
