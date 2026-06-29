# Fin Research Agent

本地优先、证据可追溯的财务研究平台。

Fin Research Agent 帮你把公开财务数据、行情、公告文档和研究记录整理到本地数据库中，再由 Python 完成指标计算、规则检查和报告生成。它不是“AI 推荐股票”的工具，而是一个面向投研工作流的本地研究终端。

> 仅用于研究和学习，不构成个性化投资建议。不包含券商登录、自动交易或自动下单。

## 适合谁

- 想用免费或低成本数据源搭建本地投研系统的人。
- 想把 A 股公司财务数据、行情、公告和研究报告统一管理的人。
- 想做可追溯研究，而不是只得到一段无法核验的 AI 总结的人。
- 想从 CLI 原型逐步产品化到 Web App 的开发者。

## 工作流

```text
输入股票代码
  -> 同步公司资料、财务报表和行情
  -> 保存原始来源、结构化财务事实和价格
  -> Python 计算利润率、现金流质量、负债率等指标
  -> 检索本地公告/年报/研究文档
  -> 生成结构化分析和可读报告
  -> 人工核验关键数字与引用
```

核心原则：

1. 数据库保存事实。
2. Python 负责计算。
3. 文档负责证据。
4. AI 只负责解释，可完全关闭。

## 功能

- A 股数据同步：通过可选 AKShare 获取公司资料、财务报表和日行情。
- 结构化财务事实：保存指标代码、报告期、发布日期、来源、口径和抓取时间。
- 历史时点分析：按 `publication_date` 过滤，降低未来数据泄漏风险。
- 文档库：导入文本、Markdown、CSV、JSON；安装 `pypdf` 后可导入 PDF。
- 文档检索：保存文档 chunk 和来源元数据，用于研究证据。
- 研究报告：先生成结构化分析结果，再渲染为 Markdown。
- 任务队列：使用数据库 `jobs` 表和普通 Python worker，不依赖 Redis/Celery。
- Web API：FastAPI 提供公司、财务、价格、文档、研究、市场、筛选器、自选股和任务接口。
- 官方公告来源：统一注册 CNINFO、上交所、深交所、北交所和可选 SEC EDGAR，保存公告元数据、原始文件 hash、页码级文档 chunk 和数据质量状态。
- 专业财务分析：确定性 Python 生成通用分析、银行行业包、消费/制造行业包、质量评分、风险提示和证据地图。
- 同业与估值实验室：本地 peer set、同业指标矩阵、增强筛选器、相对估值和简化 owner earnings 情景 DCF；展示假设、敏感性、证据和限制，不输出目标价或买卖评级。
- 机构报告层：构建 Research Evidence Bundle，生成可验证的机构风格报告，提供验证状态、证据覆盖、Markdown/JSON/打印友好 HTML 导出；AI 解释层默认关闭，启用后也必须通过证据和禁用词校验。
- 组合研究工作台：本地手工组合、观察项、风险快照、表现分析、研究提醒、日历和组合报告；不是券商账户，不自动交易，不输出调仓建议。
- 前端：Next.js 工作台、市场终端、股票筛选器和公司图表页。
- 可选 AI：预留 Ollama 本地模型接口；默认关闭。
- 可选互联网连接器：内置普通网页和 RSS；Agent Reach 可作为外部安装的互联网能力层接入。

## 项目结构

```text
.
├── backend/
│   ├── src/finresearch/
│   │   ├── api/              # FastAPI routes
│   │   ├── services/         # 业务流程：同步、分析、研究、任务
│   │   ├── repositories/     # 数据库读写边界
│   │   ├── data_sources/     # AKShare、SEC、后续官方公告源
│   │   ├── connectors/       # web/rss/agent-reach internet leads
│   │   ├── database/         # SQLAlchemy models/session
│   │   ├── documents/        # 文档解析、切块、存储
│   │   ├── ai/               # Ollama 等本地 AI provider
│   │   ├── cli/
│   │   └── worker.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   └── src/                  # Next.js App Router UI
├── app/                      # 兼容旧 CLI 的本地模块
├── tests/                    # 旧 CLI/核心模块测试
├── data/
│   ├── documents/
│   ├── raw/
│   ├── reports/
│   └── exports/
├── Makefile
└── README.md
```

## 快速开始

最简单方式：

```bash
./START_HERE.command
```

在 macOS 上也可以直接双击 `START_HERE.command`。首次启动会自动安装前端依赖、创建环境文件、启动后端 API、启动 worker、启动前端，并打开浏览器。

启动后打开：

```text
http://localhost:3000
```

页面里的 `One-Click Research Console` 可以直接输入股票代码，然后点击：

- `Sync Data`：同步数据并创建任务。
- `Open Company`：打开公司管理页。
- `Generate Report`：生成研究报告。

### 1. 安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pip install -e 'backend[dev]'
```

可选：

```bash
pip install akshare   # A 股数据同步
pip install pypdf     # PDF 文本提取
```

Agent Reach 是可选外部工具，不会随本项目默认安装。需要全网语义搜索、雪球、YouTube、Twitter/X、Reddit、小红书等渠道时，单独安装并启用：

```bash
pipx install agent-reach
agent-reach doctor
```

然后设置：

```env
AGENT_REACH_ENABLED=true
EXA_ENABLED=true
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

默认使用本地 SQLite；PostgreSQL 建议通过 Alembic 迁移初始化：

```bash
PYTHONPATH=.:backend/src alembic upgrade head
```

```env
DATABASE_URL=sqlite:///../data/finresearch.sqlite
```

如果使用 PostgreSQL：

```bash
make postgres-config
```

按提示输入本地 Postgres 的 host、port、database、user、password。脚本会写入 `backend/.env`。

也可以手动设置：

```env
DATABASE_URL=postgresql+psycopg://finresearch@localhost:5432/finresearch
```

一键启动脚本会读取 `backend/.env`。切换数据库后需要重启后端和 worker。首次连接新数据库时，后端会自动创建表结构。

### 3. 启动后端

```bash
make api
```

API 地址：

```text
http://localhost:8000
```

健康检查：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/version
curl http://localhost:8000/v1/system/config-check
```

### 4. 启动 worker

```bash
make worker
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：

```text
http://localhost:3000
```

## 常用命令

生产配置校验和本地 release smoke：

```bash
make config-check
make release-smoke
make sqlite-alembic-smoke
```

同步 A 股数据：

```bash
PYTHONPATH=.:backend/src python -m finresearch.cli.main sync 600519 --years 5
```

生成结构化分析：

```bash
PYTHONPATH=.:backend/src python -m finresearch.cli.main analyze 600519 --years 5 --output data/reports/600519.md
```

生成专业分析 API 报告：

```bash
curl 'http://localhost:8000/v1/companies/600519/analysis?include_markdown=true&strict_as_of=true'
```

专业分析不是投资建议。评分只说明研究质量、缺失数据和风险提示，不是交易信号，也不包含目标价。

同业与估值实验室：

```bash
curl 'http://localhost:8000/v1/companies/600519/peers'
curl 'http://localhost:8000/v1/companies/600519/peer-metrics'
curl 'http://localhost:8000/v1/companies/600519/valuation?model_type=relative_valuation'
curl 'http://localhost:8000/v1/companies/600519/valuation?model_type=dcf_owner_earnings'
```

估值实验室只输出估值情景范围、相对分位、假设、敏感性和限制；不是投资建议，不包含目标价、买入、卖出或持有结论。

创建同步任务：

```bash
curl -X POST http://localhost:8000/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"600519","years":5,"job_type":"sync_company"}'
```

查询公司分析摘要：

```bash
curl http://localhost:8000/v1/companies/600519/summary
```

旧 CLI 仍可使用：

```bash
finresearch sync 600519 --years 5
finresearch facts 600519 --years 5
finresearch analyze 600519 --years 5
```

## API

```text
GET  /health
GET  /ready
GET  /version
GET  /v1/system/status
GET  /v1/system/config-check

GET  /v1/companies/search?q=600519
GET  /v1/companies/{symbol}
GET  /v1/companies/{symbol}/summary
GET  /v1/companies/{symbol}/financials
GET  /v1/companies/{symbol}/metrics
GET  /v1/companies/{symbol}/prices
GET  /v1/companies/{symbol}/peers
POST /v1/companies/{symbol}/peers
GET  /v1/companies/{symbol}/peer-metrics
POST /v1/companies/{symbol}/peer-metrics
GET  /v1/companies/{symbol}/valuation
POST /v1/companies/{symbol}/valuation
GET  /v1/companies/{symbol}/valuation/runs
GET  /v1/valuation/runs/{run_id}
POST /v1/screener/query
GET  /v1/screener/presets
POST /v1/screener/presets
GET  /v1/screener/export

POST /v1/jobs
GET  /v1/jobs/{job_id}

GET  /v1/documents
POST /v1/documents/search

GET  /v1/connectors
POST /v1/connectors/health-check
GET  /v1/external-sources
POST /v1/external-sources/search
POST /v1/external-sources/read

POST /v1/research-runs
GET  /v1/research-runs
GET  /v1/research-runs/{id}
GET  /v1/research-runs/{id}/status

GET  /v1/ai/status
POST /v1/ai/warmup

GET  /v1/watchlists
POST /v1/watchlists/items
```

## 数据库

后端使用 SQLAlchemy ORM。默认 SQLite，设置 `DATABASE_URL` 后可切换 PostgreSQL。

主要实体：

- `companies`
- `filings`
- `financial_facts`
- `prices`
- `documents`
- `document_chunks`
- `research_runs`
- `citations`
- `watchlists`
- `watchlist_items`
- `jobs`
- `sync_errors`
- `external_sources`
- `company_external_sources`
- `connector_status`

`financial_facts` 是核心表。一个财务数字不仅保存数值，还保存报告期、发布日期、来源、数据口径、质量状态和抓取时间。

## 数据来源

第一阶段：

- AKShare：快速获取 A 股公司资料、财务报表和行情。
- 本地文档：年报、公告、研究笔记、CSV/JSON。
- 普通网页：本地 HTTP 读取和文本清洗。
- RSS：稳定、低维护的新闻/公告订阅渠道。
- Agent Reach：可选互联网能力层，用于 Exa、雪球、YouTube、Twitter/X、Reddit、小红书等线索来源。
- SEC Company Facts：美股结构化事实接口保留在旧 CLI 模块中。

Agent Reach 的定位是“互联网眼睛”，不是财务事实数据库。来自社区、媒体、视频、社交平台的内容会进入 `external_sources`，默认标记为 `unverified`，不能直接写入 `financial_facts`。

后续计划：

- 巨潮资讯公告列表和 PDF 下载。
- 上交所、深交所、北交所公告源。
- 官方报告页码级核验。
- 原始 JSON/PDF 归档到 `data/raw` 和 `data/documents`。

## AI 策略

默认关闭 AI。

可选 Ollama：

```env
LLM_ENABLED=false
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_CONNECT_TIMEOUT_SECONDS=2
OLLAMA_GENERATE_TIMEOUT_SECONDS=45
OLLAMA_KEEP_ALIVE=10m
```

`POST /v1/research-runs` 只创建后台任务并立即返回 `job_id` 与 `research_run_id`。
外部来源、Agent Reach/Exa、网页读取、Ollama 生成和报告组装都由 Python worker 执行。
Ollama 不可用时，任务会保留确定性的 Python 基础报告并在报告中写明本地模型不可用。

AI 只用于：

- 总结结构化分析结果。
- 解释风险提示。
- 整理报告语言。
- 文档问答。

AI 不用于：

- 财务计算。
- 数据入库判断。
- 股价预测。
- 自动买卖决定。

## 开发

运行测试：

```bash
make test
```

Lint：

```bash
make lint
```

直接运行：

```bash
PYTHONPATH=.:backend/src pytest -q
ruff check .
```

前端检查：

```bash
cd frontend
npm test
npx tsc --noEmit
npm run build
npm run test:e2e -- --project=chromium
```

## 数据库迁移

正式迁移使用 Alembic：

```bash
PYTHONPATH=.:backend/src alembic upgrade head
```

PostgreSQL 优先通过 `DATABASE_URL` 指定连接；SQLite 仅用于本地兼容和测试。`Base.metadata.create_all()` 只保留在测试、SQLite 兼容或显式 `FINRESEARCH_AUTO_CREATE_TABLES=true` 场景，避免生产环境绕过迁移。

## API 路由

常用 Stage 2 API：

- `GET /v1/market/overview`
- `GET /v1/market/indices`
- `GET /v1/market/breadth`
- `GET /v1/market/sectors`
- `GET /v1/market/movers`
- `GET /v1/companies/{symbol}/charts`
- `GET /v1/companies/{symbol}/chart`，兼容别名
- `POST /v1/screener/query`
- `POST /v1/screens/query`，兼容别名

前端使用 canonical 路由 `/charts` 和 `/screener/query`；旧命名保留为兼容入口。

## 现阶段边界

- AKShare 是聚合来源，不是官方披露来源。
- 关键财务数字需要回到公告、年报或交易所文件核验。
- PDF 表格抽取还不是页码级审计工具。
- 前端已包含工作台、市场终端、股票筛选器和公司图表页，但专业研究 UI 仍会继续扩展。
- 数据库正式迁移已接入 Alembic；测试/SQLite 兼容路径仍可显式使用 `create_all`。
- Stage 8 是生产、安全、性能和 release 收尾；不新增 Stage 9，不接入券商，不自动交易，不输出目标价或买卖持有建议。

## 文档

- [项目状态](docs/PROJECT_STATE.md)
- [安装](docs/operations/INSTALL.md)
- [配置](docs/operations/CONFIGURATION.md)
- [迁移](docs/operations/MIGRATIONS.md)
- [备份与恢复](docs/operations/BACKUP_RESTORE.md)
- [健康检查](docs/operations/HEALTHCHECKS.md)
- [性能限制](docs/operations/PERFORMANCE.md)
- [安全模型](docs/security/SECURITY_MODEL.md)
- [威胁模型](docs/security/THREAT_MODEL.md)
- [依赖审计](docs/security/DEPENDENCY_AUDIT.md)
- [Release checklist](docs/release/RELEASE_CHECKLIST.md)
- [Known limitations](docs/release/KNOWN_LIMITATIONS.md)
- [Stage 8 生产安全发布](docs/stages/STAGE_8_PRODUCTION_SECURITY_RELEASE.md)

Stage 3 官方来源 API：

- `GET /v1/data-sources`
- `GET /v1/data-sources/{source_id}/health`
- `POST /v1/companies/{symbol}/filings/sync`
- `GET /v1/companies/{symbol}/filings`
- `GET /v1/filings/{filing_id}`
- `GET /v1/documents/{document_id}/chunks`
- `GET /v1/data-quality/summary`
- `GET /v1/companies/{symbol}/benchmark`

Live source smoke is opt-in and separate from CI:

```bash
make live-source-smoke
```

Default local/CI official source mode is fixture-backed. Use `OFFICIAL_SOURCE_MODE=live` only for explicit smoke checks; fixture success must not be reported as live source success.
