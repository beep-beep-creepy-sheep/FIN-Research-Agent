import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fin Research Agent",
  description: "Evidence-first local financial research platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <header className="border-b border-line bg-white">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
              <a href="/" className="text-lg font-semibold">Fin Research Agent</a>
              <nav className="flex gap-4 text-sm text-slate-600">
                <a href="/">Dashboard</a>
                <a href="/companies/600519">Company</a>
              </nav>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}

