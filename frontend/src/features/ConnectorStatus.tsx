import { getConnectors } from "@/lib/api";

export async function ConnectorStatus() {
  let connectors: Array<Record<string, unknown>> = [];
  try {
    connectors = await getConnectors();
  } catch {
    connectors = [];
  }

  if (!connectors.length) {
    return <p className="text-sm text-slate-600">暂时没有可用连接器。基础财务数据仍可本地同步。</p>;
  }

  return (
    <div className="space-y-2">
      {connectors.map((connector) => (
        <div key={String(connector.name ?? connector.connector)} className="rounded border border-line bg-slate-50 p-2 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span>{displayConnectorName(String(connector.name ?? connector.connector))}</span>
            <span className={`rounded px-2 py-1 text-xs ${statusClass(String(connector.status))}`}>
              {displayStatus(String(connector.status), Boolean(connector.requires_login))}
            </span>
          </div>
          {connector.last_error ? (
            <p className="mt-1 truncate text-xs text-slate-500">{String(connector.last_error)}</p>
          ) : null}
          {connector.retry_after ? (
            <p className="mt-1 text-xs text-slate-500">重试时间：{formatTime(connector.retry_after)}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function displayConnectorName(name: string) {
  if (name === "direct_web") return "网页读取";
  if (name === "rss") return "RSS 新闻";
  if (name === "agent_reach_exa") return "Agent Reach · Exa";
  if (name === "agent_reach_twitter") return "Agent Reach · Twitter/X";
  if (name === "agent_reach_xueqiu") return "Agent Reach · 雪球";
  if (name === "agent_reach_reddit") return "Agent Reach · Reddit";
  if (name === "agent_reach_youtube") return "Agent Reach · YouTube";
  if (name === "agent_reach_xiaohongshu") return "Agent Reach · 小红书";
  return name;
}

function displayStatus(status: string, requiresLogin: boolean) {
  if (status === "available") return "可用";
  if (status === "disabled") return "未启用";
  if (status === "not_installed") return "未安装";
  if (status === "needs_configuration") return "未配置";
  if (status === "requires_login" || requiresLogin) return "需要登录";
  if (status === "circuit_open") return "暂时熔断";
  if (status === "unavailable") return "不可用";
  return status;
}

function statusClass(status: string) {
  if (status === "available") return "bg-emerald-100 text-emerald-800";
  if (status === "circuit_open") return "bg-amber-100 text-amber-900";
  if (status === "disabled") return "bg-slate-100 text-slate-700";
  return "bg-rose-100 text-rose-800";
}

function formatTime(value: unknown) {
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString("zh-CN");
}
