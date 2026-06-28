import { expect, test } from "@playwright/test";

test("home links to market terminal and screener", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "财务研究工作台" })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开市场终端" })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开筛选器" })).toBeVisible();
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
  await page.getByRole("button", { name: "运行筛选" }).click();
  await expect(page.getByText(/返回 \d+ 条，本地来源：financial_facts/)).toBeVisible();
});

test("company page shows chart suite empty and real financial chart states", async ({ page }) => {
  await page.goto("/companies/600519");
  await expect(page.getByRole("heading", { name: "研究摘要" })).toBeVisible();
  await expect(page.getByText("同步财务数据后，这里会生成自动研究摘要。")).toBeVisible();
  await expect(page.getByText("本地数据库里还没有该公司的财务期间数据。")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Professional Analysis" })).toBeVisible();
  await expect(page.getByText(/专业分析暂不可用|deterministic findings|explicit missing-data findings/)).toBeVisible();
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
