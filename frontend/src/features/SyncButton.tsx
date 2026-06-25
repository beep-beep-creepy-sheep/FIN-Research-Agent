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
      setMessage(`Job ${job.id ?? ""} queued`);
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "Sync failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="text-right">
      <Button onClick={sync} disabled={pending}>{pending ? "Queuing..." : "Sync Data"}</Button>
      {message ? <p className="mt-2 text-xs text-slate-600">{message}</p> : null}
    </div>
  );
}
