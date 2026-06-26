import { Card } from "@/components/Card";
import { ConnectorStatus } from "@/features/ConnectorStatus";
import { DocumentUploader } from "@/features/DocumentUploader";
import { ResearchConsole } from "@/features/ResearchConsole";
import { ResearchRuns } from "@/features/ResearchRuns";
import { SearchCompany } from "@/features/SearchCompany";
import Link from "next/link";

export default function DashboardPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-8">
        <p className="text-sm font-medium text-accent">本地优先 · 免费数据源 · 证据可追溯</p>
        <h1 className="mt-2 text-3xl font-semibold">财务研究工作台</h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          输入股票代码，一键抓取公开数据、计算核心指标，并生成带证据链的研究记录。默认示例
          600519 是贵州茅台的 A 股代码。
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card title="一键研究">
          <ResearchConsole />
        </Card>
        <Card title="现在能做什么">
          <div className="space-y-3 text-sm text-slate-700">
            <p>1. 输入公司代码，比如 600519、AAPL。</p>
            <p>2. 点击同步数据，把公开数据保存到本地 Postgres。</p>
            <p>3. 打开公司页，查看指标、证据和数据缺口。</p>
          </div>
        </Card>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Card title="快速打开公司">
          <SearchCompany />
        </Card>
        <Card title="任务中心">
          <div className="space-y-3 text-sm text-slate-600">
            <p>同步和市场快照会进入本地 jobs 表。点击后稍等几秒，再进入对应页面看结果。</p>
            <Link href="/market" className="inline-block font-medium text-accent">
              打开市场终端
            </Link>
          </div>
        </Card>
        <Card title="外部连接器">
          <ConnectorStatus />
        </Card>
      </div>
      <div className="mt-4">
        <Card title="文档证据库">
          <DocumentUploader />
        </Card>
      </div>
      <div className="mt-4">
        <Card title="最近研究记录">
          <ResearchRuns />
        </Card>
      </div>
    </main>
  );
}
