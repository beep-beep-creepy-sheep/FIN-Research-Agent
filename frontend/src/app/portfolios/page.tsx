import { Card } from "@/components/Card";
import { PortfolioDashboard } from "@/features/portfolio/PortfolioDashboard";
import { getPortfolios, type PortfolioRecord } from "@/lib/api";

export default async function PortfoliosPage() {
  let portfolios: PortfolioRecord[] = [];
  try {
    portfolios = await getPortfolios();
  } catch {
    portfolios = [];
  }
  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6">
        <p className="text-sm font-medium text-accent">Portfolio / Risk / Alerts / Calendar</p>
        <h1 className="mt-1 text-3xl font-semibold">Portfolio Research Workspace</h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          Manual portfolios and watch lists for local research. No broker connection, external push service, or automated execution.
        </p>
      </div>
      <Card title="Portfolios">
        <PortfolioDashboard initialPortfolios={portfolios} />
      </Card>
    </main>
  );
}
