# Fin Research Agent

## 中文说明

Fin Research Agent 是一个证据优先的本地财务研究工具。它现在不只是“几个命令按钮”，而是围绕 SQLite 建立了一个单用户财务研究中枢：公司资料、结构化财务事实、行情、公告/文档片段、研究记录和引用可以进入同一个本地数据库。

> 本项目用于研究、学习和投研工作流原型，不构成个性化投资建议，不包含自动交易、券商登录或下单功能。

### 核心能力

- SQLite 迁移机制：集中管理表结构，不在各模块散落 `CREATE TABLE`。
- 统一数据模型：`companies`、`financial_facts`、`prices`、`documents`、`chunks`、`research_runs`、`citations`、`sync_errors`、`watchlist`。
- 本地文档库：导入 `.txt`、`.md`、`.csv`、`.json`，安装 `pypdf` 后可导入 PDF。
- SQLite FTS5 检索：优先使用 FTS5 搜索文档片段，不可用时回退关键词评分。
- 文件 hash 去重：本地资料入库保存 `file_hash`，支持增量替换。
- A 股同步：可选安装 AKShare 后同步公司资料、财务报表和日行情。
- 结构化指标：财务事实保存 `data_source`、`retrieved_at`、`publication_date`，支持 as-of 过滤，避免未来数据泄漏。
- 一键分析：`analyze` 读取 SQLite 结构化数据，Python 计算指标，并检索本地文档证据生成 Markdown 报告。
- OpenAI 增强：保留 Web Search / File Search，用于补充信息，而不是让模型编造或心算数字。
- SEC 支持：保留 `sec-facts`，可按 CIK 拉取 US-GAAP company facts。

AKShare 是方便的聚合取数层，不是最终权威来源。正式结论仍应回到交易所公告、监管申报或公司正式报告核验。

### 项目结构

```text
.
├── app/
│   ├── analysis_pipeline.py
│   ├── ashare_client.py
│   ├── database.py
│   ├── document_store.py
│   ├── financial_store.py
│   ├── cli.py
│   └── ...
├── tests/
├── README.md
├── AGENTS.md
├── pyproject.toml
├── sample_financials.json
└── .env.example
```

### 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

可选依赖：

```bash
pip install akshare   # A 股数据同步
pip install pypdf     # PDF 文本提取
```

默认数据库路径是 `.finresearch/library.sqlite`，可以修改：

```bash
export FINRESEARCH_LIBRARY='data/library.sqlite'
```

### A 股研究流水线

同步最近 5 年数据：

```bash
finresearch sync 600519 --years 5
```

查看公司本地状态：

```bash
finresearch company 600519
```

查看结构化财务事实矩阵：

```bash
finresearch facts 600519 --years 5
```

生成本地结构化分析报告：

```bash
finresearch analyze 600519 --years 5 --output reports/600519.md
```

先同步再分析：

```bash
finresearch analyze 600519 --years 5 --sync --output reports/600519.md
```

历史时点分析，按 `publication_date` 过滤：

```bash
finresearch analyze 600519 --years 5 --as-of 2024-12-31
finresearch facts 600519 --years 5 --as-of 2024-12-31
```

### 自选股

```bash
finresearch watchlist add 600519 --note '白酒龙头'
finresearch watchlist list
finresearch watchlist sync --years 5
finresearch watchlist report --years 5
```

### 本地文档库

导入年报、笔记或公告文本：

```bash
finresearch local-ingest reports/600519_2024.md \
  --issuer 贵州茅台 \
  --report-period 2024-FY \
  --publication-date 2025-04-01 \
  --url https://example.com/report.pdf
```

检索文档证据：

```bash
finresearch local-search '现金流 风险'
```

生成本地证据简报：

```bash
finresearch local-brief '贵州茅台现金流质量和经营风险' \
  --output reports/600519_local_brief.md
```

### OpenAI 和 SEC

OpenAI Web Search / File Search：

```bash
export OPENAI_API_KEY='你的 OpenAI API Key'
export OPENAI_MODEL='gpt-5.5'

finresearch research \
  '分析 Apple 最近三年经营现金流、回购、收入增长与主要风险' \
  --domains sec.gov,apple.com \
  --output reports/apple.md
```

上传文件到 OpenAI File Search：

```bash
finresearch ingest reports/2024.pdf reports/2025.pdf
export OPENAI_VECTOR_STORE_ID='上一步输出的 vs_...'
```

SEC company facts：

```bash
finresearch sec-facts 320193 \
  --metric Revenues \
  --unit USD \
  --form 10-K \
  --user-agent 'Your Name your.email@example.com'
```

### 财务指标计算

```bash
finresearch ratios sample_financials.json
```

输出包括 `gross_margin`、`net_margin`、`cash_conversion`、`roe`、`free_cash_flow` 和 `net_debt`。

### 开发与测试

```bash
PYTHONPATH=. pytest -q
ruff check .
```

### 数据质量风险

- AKShare 上游字段和接口可能变化，所有记录都必须保留 `data_source` 和 `retrieved_at`。
- 聚合数据不等于官方披露，关键数字需要回到交易所公告或公司报告核验。
- PDF 抽取可能丢失表格结构、单位、页码、合并单元格和符号。
- as-of 分析依赖 `publication_date`，缺失发布日期会降低历史时点可信度。
- 当前 A 股公告 PDF 自动下载和交易所公告列表采集仍是后续模块。

---

## English

Fin Research Agent is an evidence-first local financial research tool. It is no longer just a set of disconnected CLI buttons: SQLite now acts as the local research hub for company profiles, structured financial facts, prices, document chunks, research runs, citations, sync errors, and watchlists.

> This project is for research, education, and workflow prototyping. It is not personalized investment advice and does not include brokerage login, order placement, or automated trading.

### Capabilities

- SQLite migrations: schema is managed centrally instead of scattered `CREATE TABLE` statements.
- Unified data model: `companies`, `financial_facts`, `prices`, `documents`, `chunks`, `research_runs`, `citations`, `sync_errors`, and `watchlist`.
- Local document library: ingest `.txt`, `.md`, `.csv`, `.json`, and PDFs when `pypdf` is installed.
- SQLite FTS5 search: document retrieval uses FTS5 when available and falls back to keyword scoring.
- File hash deduplication: ingested documents store `file_hash` for replacement and incremental updates.
- A-share sync: optional AKShare integration for company profiles, financial statements, and daily prices.
- Structured facts: records preserve `data_source`, `retrieved_at`, and `publication_date`; as-of filtering helps avoid look-ahead bias.
- One-command analysis: `analyze` reads structured SQLite facts, calculates ratios in Python, retrieves local document evidence, and renders a Markdown report.
- OpenAI enhancement: Web Search / File Search remains available for supplemental information, not for invented or mental-math financial figures.
- SEC support: `sec-facts` can fetch US-GAAP company facts by CIK.

AKShare is a convenient aggregation source, not the final authority. Material conclusions should be verified against exchange filings, regulator filings, or issuer reports.

### Repository Layout

```text
.
├── app/
│   ├── analysis_pipeline.py
│   ├── ashare_client.py
│   ├── database.py
│   ├── document_store.py
│   ├── financial_store.py
│   ├── cli.py
│   └── ...
├── tests/
├── README.md
├── AGENTS.md
├── pyproject.toml
├── sample_financials.json
└── .env.example
```

### Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Optional dependencies:

```bash
pip install akshare   # A-share data sync
pip install pypdf     # PDF text extraction
```

The default SQLite path is `.finresearch/library.sqlite`:

```bash
export FINRESEARCH_LIBRARY='data/library.sqlite'
```

### A-Share Research Pipeline

Sync five years of data:

```bash
finresearch sync 600519 --years 5
```

Inspect the local company profile:

```bash
finresearch company 600519
```

Show structured financial facts:

```bash
finresearch facts 600519 --years 5
```

Generate a local structured analysis report:

```bash
finresearch analyze 600519 --years 5 --output reports/600519.md
```

Sync first, then analyze:

```bash
finresearch analyze 600519 --years 5 --sync --output reports/600519.md
```

Point-in-time analysis with `publication_date` filtering:

```bash
finresearch analyze 600519 --years 5 --as-of 2024-12-31
finresearch facts 600519 --years 5 --as-of 2024-12-31
```

### Watchlist

```bash
finresearch watchlist add 600519 --note 'baijiu leader'
finresearch watchlist list
finresearch watchlist sync --years 5
finresearch watchlist report --years 5
```

### Local Document Library

Ingest reports, notes, or announcement text:

```bash
finresearch local-ingest reports/600519_2024.md \
  --issuer Kweichow Moutai \
  --report-period 2024-FY \
  --publication-date 2025-04-01 \
  --url https://example.com/report.pdf
```

Search evidence snippets:

```bash
finresearch local-search 'cash flow risk'
```

Generate a local evidence brief:

```bash
finresearch local-brief 'Kweichow Moutai cash-flow quality and operating risks' \
  --output reports/600519_local_brief.md
```

### OpenAI And SEC

OpenAI Web Search / File Search:

```bash
export OPENAI_API_KEY='your OpenAI API key'
export OPENAI_MODEL='gpt-5.5'

finresearch research \
  'Analyze Apple operating cash flow, buybacks, revenue growth, and key risks over the last three years' \
  --domains sec.gov,apple.com \
  --output reports/apple.md
```

Upload files to OpenAI File Search:

```bash
finresearch ingest reports/2024.pdf reports/2025.pdf
export OPENAI_VECTOR_STORE_ID='the vs_... printed by the previous command'
```

SEC company facts:

```bash
finresearch sec-facts 320193 \
  --metric Revenues \
  --unit USD \
  --form 10-K \
  --user-agent 'Your Name your.email@example.com'
```

### Ratio Calculation

```bash
finresearch ratios sample_financials.json
```

Outputs include `gross_margin`, `net_margin`, `cash_conversion`, `roe`, `free_cash_flow`, and `net_debt`.

### Development And Tests

```bash
PYTHONPATH=. pytest -q
ruff check .
```

### Data Quality Risks

- AKShare upstream fields and APIs may change; every record keeps `data_source` and `retrieved_at`.
- Aggregated data is not official disclosure; key figures need filing-level verification.
- PDF extraction can lose table structure, units, page references, merged cells, or signs.
- As-of analysis depends on `publication_date`; missing publication dates reduce point-in-time reliability.
- Automatic A-share filing list collection and official PDF download are still future modules.
