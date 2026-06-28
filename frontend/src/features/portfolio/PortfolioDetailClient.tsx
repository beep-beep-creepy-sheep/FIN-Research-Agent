"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import {
  addPortfolioHolding,
  addPortfolioWatchItem,
  createCalendarEvent,
  createPortfolioAlertRule,
  evaluatePortfolioAlerts,
  getPortfolioExposure,
  getPortfolioPerformance,
  getPortfolioReport,
  getPortfolioRisk,
  getPortfolioSummary,
} from "@/lib/api";

export function PortfolioDetailClient({
  portfolioId,
  initialPortfolio,
  initialSummary,
  initialExposure,
  initialRisk,
  initialPerformance,
  initialReport,
}: {
  portfolioId: string;
  initialPortfolio: Record<string, unknown>;
  initialSummary: Record<string, unknown> | null;
  initialExposure: Record<string, unknown> | null;
  initialRisk: Record<string, unknown> | null;
  initialPerformance: Record<string, unknown> | null;
  initialReport: Record<string, unknown> | null;
}) {
  const [portfolio, setPortfolio] = useState(initialPortfolio);
  const [summary, setSummary] = useState(initialSummary);
  const [exposure, setExposure] = useState(initialExposure);
  const [risk, setRisk] = useState(initialRisk);
  const [performance, setPerformance] = useState(initialPerformance);
  const [report, setReport] = useState(initialReport);
  const [symbol, setSymbol] = useState("600519");
  const [status, setStatus] = useState<string | null>(null);

  async function refresh() {
    const [nextSummary, nextExposure, nextRisk, nextPerformance, nextReport] = await Promise.all([
      getPortfolioSummary(portfolioId),
      getPortfolioExposure(portfolioId),
      getPortfolioRisk(portfolioId),
      getPortfolioPerformance(portfolioId),
      getPortfolioReport(portfolioId),
    ]);
    setSummary(nextSummary);
    setExposure(nextExposure);
    setRisk(nextRisk);
    setPerformance(nextPerformance);
    setReport(nextReport);
  }

  async function addWatch() {
    await addPortfolioWatchItem(portfolioId, { symbol, thesis: "Local research watch item" });
    setStatus("watch item added");
    setPortfolio({ ...portfolio, watch_items: [...asArray(portfolio.watch_items), { symbol }] });
    await refresh();
  }

  async function addPosition() {
    await addPortfolioHolding(portfolioId, { symbol, quantity: 10, cost_basis: 8, cost_currency: "CNY" });
    setStatus("position added");
    await refresh();
  }

  async function addRuleAndEvaluate() {
    await createPortfolioAlertRule(portfolioId, { symbol, rule_type: "price_above", threshold: 10, severity: "medium" });
    const result = await evaluatePortfolioAlerts(portfolioId);
    setStatus(`alerts evaluated: ${asArray(result.triggered).length} triggered`);
    await refresh();
  }

  async function addCalendar() {
    await createCalendarEvent({ portfolio_id: Number(portfolioId), symbol, title: "Manual research reminder", event_date: "2026-06-28" });
    setStatus("calendar event added");
  }

  return (
    <div className="space-y-4">
      <div className="rounded border border-line bg-slate-50 p-3 text-sm text-slate-700">
        Not investment advice. This page tracks local research exposure, risk flags, alerts, and known events only.
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto_auto_auto]">
        <input className="rounded border border-line px-3 py-2 text-sm" value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} />
        <Button onClick={addWatch}>Add Watch Item</Button>
        <Button onClick={addPosition}>Add Position</Button>
        <Button onClick={addRuleAndEvaluate}>Evaluate Alert</Button>
        <Button onClick={addCalendar}>Add Event</Button>
      </div>
      {status ? <p className="text-sm text-slate-600">{status}</p> : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Summary" data={summary} empty="No summary yet. Add a watch item or position." />
        <Panel title="Exposure" data={exposure} empty="Exposure is unavailable until local symbols are added." />
        <Panel title="Risk" data={risk} empty="Risk snapshot has insufficient data." />
        <Panel title="Performance" data={performance} empty="Performance needs local price history and weights." />
        <Panel title="Alerts" data={{ rules: portfolio.alert_rules, events: portfolio.alert_events }} empty="No alert events yet." />
        <Panel title="Calendar" data={{ events: portfolio.calendar_events }} empty="No known calendar events." />
      </div>
      <Panel title="Portfolio Report" data={report} empty="Portfolio report will render with missing-data sections when evidence is sparse." />
    </div>
  );
}

function Panel({ title, data, empty }: { title: string; data: unknown; empty: string }) {
  const available = data && JSON.stringify(data) !== "{}" && JSON.stringify(data) !== "null";
  return (
    <section className="rounded-md border border-line bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase text-slate-500">{title}</h2>
      {available ? (
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-slate-700">
          {JSON.stringify(data, null, 2)}
        </pre>
      ) : (
        <p className="rounded border border-line bg-slate-50 p-3 text-sm text-slate-600">{empty}</p>
      )}
    </section>
  );
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}
