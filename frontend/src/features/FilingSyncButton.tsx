"use client";

import { useState } from "react";
import { createOfficialFilingSyncJob } from "@/lib/api";
import { Button } from "@/components/Button";

export function FilingSyncButton({ symbol }: { symbol: string }) {
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState(false);

  async function syncFilings() {
    setBusy(true);
    setStatus("retrying");
    try {
      const job = await createOfficialFilingSyncJob(symbol);
      setStatus(`job ${String(job.id)} queued`);
    } catch (exc) {
      setStatus(exc instanceof Error ? exc.message : "sync failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Button onClick={syncFilings} disabled={busy}>
        {busy ? "Syncing" : "Sync Filings"}
      </Button>
      {status ? <span className="text-xs text-slate-500">{status}</span> : null}
    </div>
  );
}
