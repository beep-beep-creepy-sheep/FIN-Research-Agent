import { Card } from "@/components/Card";
import { SearchCompany } from "@/features/SearchCompany";

export default function DashboardPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold">Local financial research terminal</h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          Sync free local data, inspect evidence, calculate metrics in Python, and generate traceable research reports.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Company Search">
          <SearchCompany />
        </Card>
        <Card title="Data Quality">
          <p className="text-sm text-slate-600">AKShare records are marked as aggregation data until verified by official filings.</p>
        </Card>
        <Card title="Task Center">
          <p className="text-sm text-slate-600">Create sync jobs from the company page and poll status through the API.</p>
        </Card>
      </div>
    </main>
  );
}

