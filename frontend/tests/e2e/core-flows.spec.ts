import { expect, test } from "@playwright/test";

test("home links to market terminal and screener", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "财务研究工作台" })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开市场终端" })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开筛选器" })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开组合工作台" })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开日历" })).toBeVisible();
});

test("market terminal renders professional empty states and sources", async ({ page }) => {
  await page.goto("/market");
  await expect(page.getByRole("heading", { name: "市场终端" })).toBeVisible();
  await expect(page.getByText("涨跌家数")).toBeVisible();
  await expect(page.getByText("来源：本地 PostgreSQL/SQLite 行情快照；无数据时不造点。").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "数据质量" })).toBeVisible();
});

test("screener can query local financial facts", async ({ page }) => {
  await page.goto("/screener");
  await expect(page.getByRole("heading", { name: "股票筛选器" })).toBeVisible();
  await page.getByPlaceholder("最低净利率，%").fill("20");
  await page.getByLabel("include_missing").check();
  await page.getByRole("button", { name: "运行筛选" }).click();
  await expect(page.getByText(/返回 \d+ 条，本地来源：financial_facts/)).toBeVisible();
  await expect(page.getByText("导出 CSV")).toBeVisible();
});

test("company page shows chart suite empty and real financial chart states", async ({ page }) => {
  await page.goto("/companies/600519");
  await expect(page.getByRole("heading", { name: "研究摘要" })).toBeVisible();
  await expect(page.getByText("同步财务数据后，这里会生成自动研究摘要。")).toBeVisible();
  await expect(page.getByText("本地数据库里还没有该公司的财务期间数据。")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Professional Analysis" })).toBeVisible();
  await expect(page.getByText(/专业分析暂不可用|deterministic findings|explicit missing-data findings/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Peers" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Peer Metrics Matrix" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Valuation Lab" })).toBeVisible();
  await expect(page.getByText("估值情景范围、相对分位和敏感性分析仅用于研究核验，不是投资建议。")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Institutional Report" })).toBeVisible();
  await expect(page.getByText("Not investment advice. This report uses local evidence and deterministic validation before display.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Generate Report" })).toBeVisible();
  await expect(page.getByText("K线与成交量")).toBeVisible();
  await expect(page.getByText("收入 / 净利润 / 经营现金流")).toBeVisible();
  await expect(page.getByText("价格来自本地 prices 表；抓取失败时不生成替代行情。")).toBeVisible();
});

test("company page can create official filing sync job and show provenance panels", async ({ page }) => {
  await page.goto("/companies/600519");
  await expect(page.getByRole("heading", { name: "公告 / Filings" })).toBeVisible();
  await expect(page.getByText("没有公告记录。点击同步会创建后台任务；真实下载和解析由 worker 执行。")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Benchmark" })).toBeVisible();
  await expect(page.getByText("benchmark_price_missing")).toBeVisible();
  await expect(page.getByRole("heading", { name: "数据质量" })).toBeVisible();
  await expect(page.getByText("当前没有数据质量问题；这也可能表示还没有运行官方公告同步。")).toBeVisible();
  await page.getByRole("button", { name: "Sync Filings" }).click();
  await expect(page.getByText(/job \d+ queued/)).toBeVisible();
});

test("portfolio workspace can create a local research portfolio and show risk sections", async ({ page }) => {
  await page.goto("/portfolios");
  await expect(page.getByRole("heading", { name: "Portfolio Research Workspace" })).toBeVisible();
  await expect(page.getByText("Not investment advice. Portfolios are local research lists, not brokerage accounts.")).toBeVisible();
  await page.getByRole("button", { name: "Create Portfolio" }).click();
  await expect(page.getByText("created")).toBeVisible();
  await page.getByText("Local Research Portfolio").click();
  await expect(page.getByRole("heading", { name: "Exposure" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Risk" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Performance" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Alerts" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Calendar" })).toBeVisible();
  await page.getByRole("button", { name: "Add Watch Item" }).click();
  await expect(page.getByText("watch item added")).toBeVisible();
  await page.getByRole("button", { name: "Evaluate Alert" }).click();
  await expect(page.getByText(/alerts evaluated/)).toBeVisible();
});

test("calendar page shows no-known-events state and supports manual events", async ({ page }) => {
  await page.goto("/calendar");
  await expect(page.getByRole("heading", { name: "Research Calendar" })).toBeVisible();
  await expect(page.getByText("Future events are never guessed.")).toBeVisible();
  await page.getByRole("button", { name: "Add Manual Event" }).click();
  await expect(page.getByText("event added")).toBeVisible();
});

test("backend system health and config are production-safe by default", async ({ request }) => {
  const health = await request.get("http://127.0.0.1:8000/health");
  expect(health.ok()).toBeTruthy();
  expect(await health.json()).toEqual({ status: "ok" });

  const ready = await request.get("http://127.0.0.1:8000/ready");
  expect(ready.ok()).toBeTruthy();
  expect((await ready.json()).status).toBe("ready");

  const config = await request.get("http://127.0.0.1:8000/v1/system/config-check");
  expect(config.ok()).toBeTruthy();
  const payload = await config.json();
  expect(payload.status).toBe("passed");
  expect(payload.summary.llm.enabled).toBe(false);
  expect(payload.summary.external_network.run_live_source_tests).toBe(false);
  expect(JSON.stringify(payload.summary.secrets)).not.toMatch(/sk-[A-Za-z0-9]/);
  expect(JSON.stringify(payload)).not.toMatch(/password|cookie|bearer/i);
});
