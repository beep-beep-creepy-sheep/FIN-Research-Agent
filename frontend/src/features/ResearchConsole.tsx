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
  const [report, setReport] = useState("");
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
      setMessage(
        created.reused
          ? "这家公司刚同步过或正在同步，没有重复创建任务。"
          : "已创建同步任务。已有记录会更新，不会重复导入同一批财务事实。"
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "无法创建同步任务");
    } finally {
      setBusy(false);
    }
  }

  async function generateReport() {
    setBusy(true);
    setMessage("");
    try {
      const run = await createResearchRun(symbol, years);
      setReport("");
      setJob({
        id: String(run.job_id ?? ""),
        status: String(run.job_status ?? run.status ?? "queued"),
        progress: 0,
        stage: "queued",
      });
      setMessage(`已创建研究任务 #${String(run.job_id ?? "")}，研究记录 #${String(run.research_run_id ?? run.id ?? "")} 将由 worker 后台生成。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "无法创建报告任务");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
        <label className="space-y-1">
          <span className="block font-medium text-slate-700">股票代码</span>
          <Input value={symbol} onChange={(event) => setSymbol(event.target.value.trim())} placeholder="例如 600519" />
        </label>
        <label className="space-y-1">
          <span className="block font-medium text-slate-700">回看年数</span>
          <Input
            type="number"
            min={1}
            max={20}
            value={years}
            onChange={(event) => setYears(Number(event.target.value))}
          />
        </label>
      </div>
      <p className="text-xs text-slate-500">600519 = 贵州茅台。深度记录会同时尝试读取本地财务数据、PDF 证据、Agent Reach 和新闻/RSS 来源。</p>
      <div className="flex flex-wrap gap-2">
        <Button onClick={syncData} disabled={busy}>同步数据</Button>
        <Button onClick={() => (window.location.href = `/companies/${encodeURIComponent(symbol)}`)}>
          打开公司页
        </Button>
        <Button onClick={generateReport} disabled={busy}>生成深度研究记录</Button>
      </div>
      {job.id ? (
        <div className="rounded-md border border-line bg-slate-50 p-3 text-sm">
          <div className="flex justify-between">
            <span>任务 #{job.id}</span>
            <span>{translateStatus(job.status)}</span>
          </div>
          <div className="mt-2 h-2 rounded bg-slate-200">
            <div className="h-2 rounded bg-accent" style={{ width: `${job.progress ?? 0}%` }} />
          </div>
          <p className="mt-2 text-xs text-slate-500">{job.stage}</p>
        </div>
      ) : null}
      {message ? <p className="text-sm text-slate-600">{message}</p> : null}
      {report ? (
        <div className="max-h-[42rem] overflow-auto rounded-md border border-line bg-white p-4 text-sm leading-6 text-slate-700">
          {report.split("\n").map((line, index) => (
            <p key={`${index}-${line}`} className={line.startsWith("#") ? "mt-3 font-semibold text-slate-900" : ""}>
              {line.replace(/^#+\s*/, "") || "\u00a0"}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function translateStatus(status?: string) {
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  if (status === "running") return "运行中";
  if (status === "queued") return "排队中";
  return status ?? "等待中";
}
