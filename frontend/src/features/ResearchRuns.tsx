import { getResearchRuns } from "@/lib/api";

export async function ResearchRuns({ symbol }: { symbol?: string }) {
  let runs: Array<Record<string, unknown>> = [];
  try {
    runs = await getResearchRuns();
  } catch {
    runs = [];
  }
  const filtered = symbol ? runs.filter((run) => String(run.symbol) === symbol) : runs;

  if (!filtered.length) {
    return <p className="text-sm text-slate-600">还没有研究记录。点击“生成研究记录”后会生成带财务指标、外部证据和引用清单的深度记录。</p>;
  }

  return (
    <div className="space-y-3">
      {filtered.slice(0, 1).map((run, index) => {
        const markdown = String(run.report_markdown ?? "暂无内容");
        return (
          <article key={String(run.id)} className="rounded border border-line bg-slate-50 p-4 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium text-slate-900">
                {index === 0 ? "最新深度研究记录" : `历史记录 #${String(run.id)}`}
              </span>
              <span className="text-xs text-slate-500">{formatDate(run.created_at)}</span>
            </div>
            <p className="mt-2 leading-6 text-slate-700">{extractConclusion(markdown)}</p>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs font-medium text-accent">展开完整专业记录</summary>
              <div className="mt-3 max-h-[42rem] overflow-auto whitespace-pre-wrap rounded bg-white p-4 leading-6 text-slate-700">
                {markdown}
              </div>
            </details>
          </article>
        );
      })}
    </div>
  );
}

function formatDate(value: unknown) {
  if (!value) return "";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN");
}

function extractConclusion(markdown: string) {
  const lines = markdown.split("\n").map((line) => line.trim()).filter(Boolean);
  const index = lines.findIndex((line) => line.includes("一句话结论"));
  if (index >= 0 && lines[index + 1]) {
    return lines[index + 1].replace(/^[-#]+\s*/, "");
  }
  return lines.find((line) => !line.startsWith("#") && !line.startsWith("- 股票代码")) ?? "暂无摘要";
}
