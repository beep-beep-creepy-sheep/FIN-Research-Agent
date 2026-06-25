# Fin Research Agent

## 中文说明

Fin Research Agent 是一个证据优先的财务研究命令行工具。它可以在本地建立资料库、检索年报和研究文件、生成带引用的研究简报，也可以接入 OpenAI Web Search / File Search、SEC Company Facts 和 Agent Reach 作为增强数据来源。

> 本项目用于研究、学习和投研工作流原型，不构成个性化投资建议，不包含自动交易功能。

### 现在已经具备的能力

- 本地资料库：把 `.txt`、`.md`、`.csv`、`.json` 文件导入 SQLite；如安装 `pypdf`，也可导入 PDF。
- 本地检索：按关键词从资料库中检索相关片段，保留文件名、路径、报告期、发布日期和 URL 等元数据。
- 本地研究简报：根据检索结果生成 Markdown 简报，包含 Evidence Leads、Assumptions、Missing Information 和 Verification Checklist。
- OpenAI 研究：使用 Responses API 的 `web_search` 做实时联网检索，可通过 `--domains` 限制权威域名。
- OpenAI File Search：上传年报或基金报告到向量库，并在研究时按需检索。
- Agent Reach：可选调用 Exa 作为普通互联网线索来源。
- SEC Company Facts：按 CIK 拉取 SEC XBRL company facts，并抽取指定 US-GAAP 指标。
- 确定性计算：用 Python 计算毛利率、净利率、现金利润转换率、ROE、自由现金流和净负债。

### 项目结构

```text
fin-research-agent/
├── app/
│   ├── agent_reach.py      # 可选 Agent Reach 适配器
│   ├── calculator.py       # 财务指标计算
│   ├── cli.py              # Typer 命令行入口
│   ├── config.py           # 环境变量和本地资料库路径
│   ├── document_store.py   # 本地文档读取、分块、SQLite 索引和检索
│   ├── models.py           # Pydantic 数据模型
│   ├── openai_research.py  # OpenAI Web Search / File Search 客户端
│   ├── reporting.py        # 本地证据简报生成
│   └── sec_client.py       # SEC Company Facts 客户端
├── tests/
├── sample_financials.json
├── AGENTS.md
├── pyproject.toml
└── README.md
```

### 安装

```bash
cd fin-research-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
pip install -e '.[dev]'
```

如果要导入 PDF：

```bash
pip install pypdf
```

### 零 API Key 的本地流程

导入本地资料：

```bash
finresearch local-ingest reports/apple_2024.md \
  --issuer Apple \
  --report-period 2024-FY \
  --publication-date 2024-11-01 \
  --url https://investor.apple.com/
```

查看资料库：

```bash
finresearch library-list
```

检索证据片段：

```bash
finresearch local-search 'operating cash flow buybacks'
```

生成本地研究简报：

```bash
finresearch local-brief \
  'Apple 最近三年现金流质量和回购是否健康？' \
  --output reports/apple_local_brief.md
```

默认本地资料库路径是 `.finresearch/library.sqlite`。可以用环境变量或命令参数修改：

```bash
export FINRESEARCH_LIBRARY='data/library.sqlite'
finresearch local-search 'cash flow' --library data/library.sqlite
```

### OpenAI 实时研究

设置 API key：

```bash
export OPENAI_API_KEY='你的 OpenAI API Key'
export OPENAI_MODEL='gpt-5.5'
```

运行联网研究，并限制权威来源域名：

```bash
finresearch research \
  '分析 Apple 最近三年经营现金流、回购、收入增长与主要风险' \
  --domains sec.gov,apple.com \
  --output reports/apple.md
```

A 股示例：

```bash
finresearch research \
  '分析贵州茅台最近三年收入、现金流、预收款和估值风险' \
  --domains cninfo.com.cn,sse.com.cn,szse.cn,moutaichina.com
```

历史时点研究：

```bash
finresearch research \
  '截至当时公司是否出现现金流恶化？' \
  --as-of 2024-12-31
```

### OpenAI File Search

把长期反复查询的年报、季报、基金报告和内部研究资料上传到 OpenAI File Search：

```bash
finresearch ingest reports/2024.pdf reports/2025.pdf
export OPENAI_VECTOR_STORE_ID='上一步输出的 vs_...'

finresearch research \
  '结合已上传年报和最新公开信息分析现金流质量'
```

设置 `OPENAI_VECTOR_STORE_ID` 后，`research` 命令会同时使用 File Search 和 Web Search。

### SEC Company Facts

查询 SEC company facts 中的 US-GAAP 指标：

```bash
finresearch sec-facts 320193 \
  --metric Revenues \
  --unit USD \
  --form 10-K \
  --user-agent 'Your Name your.email@example.com'
```

SEC 要求合理的 `User-Agent`。生产使用时请填写真实联系方式。

### Agent Reach

Agent Reach 适合作为普通互联网线索补充，不应作为财务数字的最终来源。

```bash
finresearch doctor

finresearch research \
  '某公司的产品口碑和争议' \
  --agent-reach
```

### 财务指标计算

```bash
finresearch ratios sample_financials.json
```

输入 JSON：

```json
{
  "revenue": 1000000000,
  "gross_profit": 420000000,
  "net_profit": 90000000,
  "operating_cash_flow": 120000000,
  "capital_expenditure": 35000000,
  "equity_begin": 600000000,
  "equity_end": 680000000,
  "interest_bearing_debt": 240000000,
  "cash": 150000000
}
```

输出指标：

- `gross_margin`：毛利率
- `net_margin`：净利率
- `cash_conversion`：经营现金流 / 净利润
- `roe`：净利润 / 平均权益
- `free_cash_flow`：经营现金流 - 资本开支
- `net_debt`：有息债务 - 现金

### 开发与测试

```bash
PYTHONPATH=. pytest -q
ruff check .
```

后续建议扩展：

- SEC/EDGAR、巨潮资讯、上交所、深交所公告采集器。
- 更强的语义检索或 pgvector/FTS5 检索。
- XBRL 标准化财务数据库。
- 引用核验、数字核验、单位核验和报告期核验。
- 行业同口径对比、历史时点回测和估值情景分析。

### 安全边界

- 不要把券商密码、主账号 Cookie、交易 API 密钥交给模型。
- 不要开启无人监督的自动下单、转账或账户设置变更。
- Agent Reach、网页和社交平台内容都应视为未验证线索。
- 重要结论必须保留来源、时间点、单位、假设和可证伪条件。

---

## English

Fin Research Agent is an evidence-first financial research CLI. It can build a local document library, search annual reports and research files, generate cited Markdown briefs, and optionally use OpenAI Web Search / File Search, SEC Company Facts, and Agent Reach as enhanced data sources.

> This project is for research, education, and workflow prototyping. It is not personalized investment advice and does not include automated trading.

### What It Can Do Now

- Local library: index `.txt`, `.md`, `.csv`, and `.json` files into SQLite; PDF ingestion is available when `pypdf` is installed.
- Local retrieval: search relevant snippets while preserving file path, issuer, report period, publication date, and source URL metadata.
- Local research briefs: generate Markdown briefs with Evidence Leads, Assumptions, Missing Information, and a Verification Checklist.
- OpenAI research: use Responses API `web_search` for live web research, with domain allowlists through `--domains`.
- OpenAI File Search: upload reports to a vector store and retrieve them during research.
- Agent Reach: optionally use Exa results as general internet leads.
- SEC Company Facts: fetch SEC XBRL company facts by CIK and extract selected US-GAAP metrics.
- Deterministic calculations: compute gross margin, net margin, cash conversion, ROE, free cash flow, and net debt in Python.

### Repository Layout

```text
fin-research-agent/
├── app/
│   ├── agent_reach.py      # Optional Agent Reach adapter
│   ├── calculator.py       # Financial ratio calculations
│   ├── cli.py              # Typer CLI entrypoint
│   ├── config.py           # Environment and local library path
│   ├── document_store.py   # Local file reading, chunking, SQLite indexing, search
│   ├── models.py           # Pydantic models
│   ├── openai_research.py  # OpenAI Web Search / File Search client
│   ├── reporting.py        # Local evidence brief rendering
│   └── sec_client.py       # SEC Company Facts client
├── tests/
├── sample_financials.json
├── AGENTS.md
├── pyproject.toml
└── README.md
```

### Installation

```bash
cd fin-research-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -e '.[dev]'
```

For PDF ingestion:

```bash
pip install pypdf
```

### Local Workflow With No API Key

Index local files:

```bash
finresearch local-ingest reports/apple_2024.md \
  --issuer Apple \
  --report-period 2024-FY \
  --publication-date 2024-11-01 \
  --url https://investor.apple.com/
```

List the library:

```bash
finresearch library-list
```

Search evidence snippets:

```bash
finresearch local-search 'operating cash flow buybacks'
```

Generate a local evidence brief:

```bash
finresearch local-brief \
  'Is Apple cash-flow quality and buyback activity healthy over the last three years?' \
  --output reports/apple_local_brief.md
```

The default local library path is `.finresearch/library.sqlite`. Override it with an environment variable or command option:

```bash
export FINRESEARCH_LIBRARY='data/library.sqlite'
finresearch local-search 'cash flow' --library data/library.sqlite
```

### OpenAI Live Research

Set your API key:

```bash
export OPENAI_API_KEY='your OpenAI API key'
export OPENAI_MODEL='gpt-5.5'
```

Run web research with a primary-source domain allowlist:

```bash
finresearch research \
  'Analyze Apple operating cash flow, buybacks, revenue growth, and key risks over the last three years' \
  --domains sec.gov,apple.com \
  --output reports/apple.md
```

China A-share example:

```bash
finresearch research \
  'Analyze Kweichow Moutai revenue, cash flow, advances from customers, and valuation risks over the last three years' \
  --domains cninfo.com.cn,sse.com.cn,szse.cn,moutaichina.com
```

Point-in-time research:

```bash
finresearch research \
  'As of that date, was the company showing signs of cash-flow deterioration?' \
  --as-of 2024-12-31
```

### OpenAI File Search

Upload annual reports, quarterly reports, fund documents, or internal research files that you expect to reuse:

```bash
finresearch ingest reports/2024.pdf reports/2025.pdf
export OPENAI_VECTOR_STORE_ID='the vs_... printed by the previous command'

finresearch research \
  'Analyze cash-flow quality using the uploaded annual reports and latest public information'
```

When `OPENAI_VECTOR_STORE_ID` is set, the `research` command uses both File Search and Web Search.

### SEC Company Facts

Fetch a US-GAAP metric from SEC company facts:

```bash
finresearch sec-facts 320193 \
  --metric Revenues \
  --unit USD \
  --form 10-K \
  --user-agent 'Your Name your.email@example.com'
```

SEC expects a reasonable `User-Agent`. Use a real contact in production.

### Agent Reach

Agent Reach is useful as a supplementary internet lead source, not as the final source for financial figures.

```bash
finresearch doctor

finresearch research \
  'Research product reputation and controversies for this company' \
  --agent-reach
```

### Financial Ratio Calculation

```bash
finresearch ratios sample_financials.json
```

Input JSON:

```json
{
  "revenue": 1000000000,
  "gross_profit": 420000000,
  "net_profit": 90000000,
  "operating_cash_flow": 120000000,
  "capital_expenditure": 35000000,
  "equity_begin": 600000000,
  "equity_end": 680000000,
  "interest_bearing_debt": 240000000,
  "cash": 150000000
}
```

Outputs:

- `gross_margin`: gross profit / revenue
- `net_margin`: net profit / revenue
- `cash_conversion`: operating cash flow / net profit
- `roe`: net profit / average equity
- `free_cash_flow`: operating cash flow - capital expenditure
- `net_debt`: interest-bearing debt - cash

### Development And Tests

```bash
PYTHONPATH=. pytest -q
ruff check .
```

Suggested next steps:

- SEC/EDGAR, CNINFO, SSE, and SZSE filing collectors.
- Stronger semantic retrieval or pgvector/FTS5 retrieval.
- XBRL-normalized financial database.
- Citation, number, unit, and reporting-period verification.
- Peer comparison, point-in-time backtesting, and valuation scenario analysis.

### Safety Boundaries

- Do not give the model brokerage passwords, primary account cookies, or trading API keys.
- Do not enable unsupervised trading, transfers, or account-setting changes.
- Treat Agent Reach, web, and social-media content as unverified leads.
- Keep sources, timestamps, units, assumptions, and falsification conditions with material conclusions.
