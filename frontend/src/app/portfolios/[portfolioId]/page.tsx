import { PortfolioDetailClient } from "@/features/portfolio/PortfolioDetailClient";
import {
  getPortfolio,
  getPortfolioExposure,
  getPortfolioPerformance,
  getPortfolioReport,
  getPortfolioRisk,
  getPortfolioSummary,
} from "@/lib/api";

export default async function PortfolioDetailPage({ params }: { params: Promise<{ portfolioId: string }> }) {
  const { portfolioId } = await params;
  const portfolio = await safe(() => getPortfolio(portfolioId), { id: portfolioId, name: "Portfolio unavailable" });
  const summary = await safe(() => getPortfolioSummary(portfolioId), null);
  const exposure = await safe(() => getPortfolioExposure(portfolioId), null);
  const risk = await safe(() => getPortfolioRisk(portfolioId), null);
  const performance = await safe(() => getPortfolioPerformance(portfolioId), null);
  const report = await safe(() => getPortfolioReport(portfolioId), null);

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6">
        <p className="text-sm font-medium text-accent">Portfolio detail</p>
        <h1 className="mt-1 text-3xl font-semibold">{String(portfolio.name ?? `Portfolio ${portfolioId}`)}</h1>
        <p className="mt-2 text-slate-600">Exposure, risk, performance, alerts, calendar, and deterministic portfolio report.</p>
      </div>
      <PortfolioDetailClient
        portfolioId={portfolioId}
        initialPortfolio={portfolio}
        initialSummary={summary}
        initialExposure={exposure}
        initialRisk={risk}
        initialPerformance={performance}
        initialReport={report}
      />
    </main>
  );
}

async function safe<T>(func: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await func();
  } catch {
    return fallback;
  }
}
