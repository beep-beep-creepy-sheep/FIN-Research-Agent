import { Card } from "@/components/Card";
import { getCompanySummary } from "@/lib/api";
import { SyncButton } from "@/features/SyncButton";

export default async function CompanyPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  let summary = null;
  let error = "";
  try {
    summary = await getCompanySummary(symbol);
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Unable to load company";
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">{symbol}</h1>
          <p className="mt-1 text-slate-600">Evidence-first company workspace</p>
        </div>
        <SyncButton symbol={symbol} />
      </div>

      {error ? <div className="mb-4 rounded-md border border-risk bg-white p-4 text-sm text-risk">{error}</div> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Overview">
          <pre className="overflow-auto text-xs">{JSON.stringify(summary?.company ?? {}, null, 2)}</pre>
        </Card>
        <Card title="Calculated Metrics">
          <pre className="overflow-auto text-xs">{JSON.stringify(summary?.metrics ?? {}, null, 2)}</pre>
        </Card>
        <Card title="Financial Periods">
          <pre className="max-h-96 overflow-auto text-xs">{JSON.stringify(summary?.periods ?? [], null, 2)}</pre>
        </Card>
        <Card title="Evidence">
          <pre className="max-h-96 overflow-auto text-xs">{JSON.stringify(summary?.evidence ?? [], null, 2)}</pre>
        </Card>
      </div>
    </main>
  );
}

