"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { createMarketSnapshotJob } from "@/lib/api";

export function MarketRefreshButton({ market = "CN" }: { market?: string }) {
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    setStatus("");
    try {
      const job = await createMarketSnapshotJob(market);
      setStatus(`任务 ${String(job.id)} 已创建：${String(job.status)}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "创建任务失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <Button onClick={refresh} disabled={loading}>
        {loading ? "创建中" : "刷新市场快照"}
      </Button>
      {status ? <p className="text-xs text-slate-500">{status}</p> : null}
    </div>
  );
}
