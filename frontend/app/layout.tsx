import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ODIN — Intelligence Console",
  description:
    "Personal internet intelligence engine — emerging events, trend momentum and opportunities.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col font-sans">
        <Providers>
          <header className="border-b border-border/80 backdrop-blur-sm sticky top-0 z-10 bg-bg/70">
            <div className="mx-auto max-w-6xl px-6 py-4 flex items-center gap-3">
              <div className="size-6 rounded-full border border-accent/60 grid place-items-center">
                <div className="size-1.5 rounded-full bg-accent" />
              </div>
              <span className="font-mono text-sm tracking-[0.3em] text-text">ODIN</span>
              <span className="text-muted text-xs tracking-widest uppercase">
                Intelligence Console
              </span>
            </div>
          </header>
          <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
