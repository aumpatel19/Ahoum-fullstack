import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Navbar } from "@/components/Navbar";
import { Providers } from "@/app/providers";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Ahoum — Sessions",
  description: "Find a session, book a seat.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-bg font-sans">
        <Providers>
          <Navbar />
          <main className="pb-20">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
