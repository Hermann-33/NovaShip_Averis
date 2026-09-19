import type { Metadata } from "next";
import "./globals.css";
import { Shell } from "@/components/shell";

export const metadata: Metadata = {
  title: "NovaShip Averis — Shipping Inbox & SI↔BL Verification",
  description: "AI-assisted shipping operations control center: secure inbox, seven-field SI vs Draft BL verification, human-approved actions, full audit.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ink-50 text-ink-900 antialiased">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
