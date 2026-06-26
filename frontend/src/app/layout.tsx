import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FIN Research Agent",
  description: "本地优先的财务研究工作台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="min-h-screen">
          <header className="border-b border-line bg-white">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
              <a href="/" className="text-lg font-semibold">FIN Research Agent</a>
              <nav className="flex gap-4 text-sm text-slate-600">
                <a href="/">工作台</a>
                <a href="/companies/600519">示例公司</a>
              </nav>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
