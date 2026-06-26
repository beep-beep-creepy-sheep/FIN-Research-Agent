"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { createResearchRun, createSyncJob, getJob } from "@/lib/api";

type JobState = {
  id?: string;
  status?: string;
  progress?: number;
  stage?: string;
};

export function ResearchConsole() {
  const [symbol, setSymbol] = useState("600519");
  const [years, setYears] = useState(5);
  const [job, setJob] = useState<JobState>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!job.id || job.status === "completed" || job.status === "failed") {
      return;
    }
    const timer = window.setInterval(async () => {
      const current = await getJob(job.id as string);
      setJob({
        id: String(current.id),
        status: String(current.status),
        progress: Number(current.progress ?? 0),
        stage: String(current.current_stage ?? ""),
      });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [job.id, job.status]);

  async function syncData() {
    setBusy(true);
    setMessage("");
    try {
      const created = await createSyncJob(symbol, years);
      setJob({
        id: String(created.id),
        status: String(created.status),
        progress: Number(created.progress ?? 0),
        stage: String(created.current_stage ?? ""),
      });
      setMessage("Sync job queued. Keep the worker running.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to create sync job");
    } finally {
      setBusy(false);
    }
  }

  async function generateReport() {
    setBusy(true);
    setMessage("");
    try {
      const run = await createResearchRun(symbol, years);
      setMessage(`Research run created: ${String(run.id ?? "")}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to create report");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-[1fr_120px]">
        <Input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="600519" />
        <Input
          type="number"
          min={1}
          max={20}
          value={years}
          onChange={(event) => setYears(Number(event.target.value))}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={syncData} disabled={busy}>Sync Data</Button>
        <Button onClick={() => (window.location.href = `/companies/${encodeURIComponent(symbol)}`)}>
          Open Company
        </Button>
        <Button onClick={generateReport} disabled={busy}>Generate Report</Button>
      </div>
      {job.id ? (
        <div className="rounded-md border border-line bg-slate-50 p-3 text-sm">
          <div className="flex justify-between">
            <span>Job #{job.id}</span>
            <span>{job.status}</span>
          </div>
          <div className="mt-2 h-2 rounded bg-slate-200">
            <div className="h-2 rounded bg-accent" style={{ width: `${job.progress ?? 0}%` }} />
          </div>
          <p className="mt-2 text-xs text-slate-500">{job.stage}</p>
        </div>
      ) : null}
      {message ? <p className="text-sm text-slate-600">{message}</p> : null}
    </div>
  );
}
