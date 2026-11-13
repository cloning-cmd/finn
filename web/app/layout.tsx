import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import BottomNav from "@/components/BottomNav";
import SwRegister from "@/components/SwRegister";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "FINN",
  description: "Inbox-zero for your Indian equity portfolio.",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "FINN" },
  icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
};
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#09090b" },
    { media: "(prefers-color-scheme: light)", color: "#f5f6f8" },
  ],
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <div className="mx-auto min-h-dvh max-w-[560px] px-4 pb-28 md:max-w-[720px] md:px-6" style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}>
          {children}
        </div>
        <BottomNav />
        <SwRegister />
      </body>
    </html>
  );
}
