"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { createSyncJob } from "@/lib/api";

export function SyncButton({ symbol }: { symbol: string }) {
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  async function sync() {
    setPending(true);
    setMessage("");
    try {
      const job = await createSyncJob(symbol, 5);
      setMessage(
        job.reused
          ? `任务 ${job.id ?? ""} 已存在，没有重复创建`
          : `任务 ${job.id ?? ""} 已创建，不会重复导入`
      );
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "同步失败");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="text-right">
      <Button onClick={sync} disabled={pending}>{pending ? "创建中..." : "同步数据"}</Button>
      {message ? <p className="mt-2 text-xs text-slate-600">{message}</p> : null}
    </div>
  );
}
