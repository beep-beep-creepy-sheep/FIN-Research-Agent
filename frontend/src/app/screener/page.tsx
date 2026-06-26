import Link from "next/link";
import { ScreenerClient } from "@/features/screener/ScreenerClient";

export default function ScreenerPage() {
  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-accent">Screener · 本地财务事实</p>
          <h1 className="mt-1 text-3xl font-semibold">股票筛选器</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            基于本地数据库最新财务期间筛选公司。没有同步过的数据不会被模拟或补全。
          </p>
        </div>
        <Link href="/market" className="rounded-md border border-line bg-white px-3 py-2 text-sm font-medium">
          市场终端
        </Link>
      </div>
      <ScreenerClient />
    </main>
  );
}
