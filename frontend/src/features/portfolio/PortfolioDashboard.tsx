"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/Button";
import { createPortfolio, type PortfolioRecord } from "@/lib/api";

export function PortfolioDashboard({ initialPortfolios }: { initialPortfolios: PortfolioRecord[] }) {
  const [portfolios, setPortfolios] = useState(initialPortfolios);
  const [name, setName] = useState("Local Research Portfolio");
  const [status, setStatus] = useState<string | null>(null);

  async function submit() {
    setStatus("creating");
    try {
      const created = await createPortfolio({
        name,
        portfolio_type: "watchlist",
        base_currency: "CNY",
        description: "Local research workspace",
      });
      setPortfolios((current) => [...current, created]);
      setStatus("created");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "create_failed");
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded border border-line bg-slate-50 p-3 text-sm text-slate-700">
        Not investment advice. Portfolios are local research lists, not brokerage accounts.
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
        <input
          className="rounded border border-line px-3 py-2 text-sm"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Portfolio name"
        />
        <Button onClick={submit}>Create Portfolio</Button>
      </div>
      {status ? <p className="text-sm text-slate-600">{status}</p> : null}
      {portfolios.length ? (
        <div className="grid gap-3">
          {portfolios.map((portfolio) => (
            <Link key={portfolio.id} href={`/portfolios/${portfolio.id}`} className="rounded border border-line bg-white p-4 hover:border-accent">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium text-slate-900">{portfolio.name}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {portfolio.portfolio_type} · {portfolio.base_currency}
                  </div>
                </div>
                <div className="text-right text-xs text-slate-500">
                  <div>{portfolio.holdings_count ?? 0} positions</div>
                  <div>{portfolio.watch_count ?? 0} watch items</div>
                  <div>{portfolio.open_alerts ?? 0} open alerts</div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <p className="rounded border border-line bg-white p-3 text-sm text-slate-600">
          No portfolios yet. Create a local research list to track exposure, risk, alerts, and calendar events.
        </p>
      )}
    </div>
  );
}
