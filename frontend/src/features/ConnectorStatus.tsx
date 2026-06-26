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
        <div key={String(connector.name)} className="flex items-center justify-between text-sm">
          <span>{displayConnectorName(String(connector.name))}</span>
          <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-700">
            {displayStatus(String(connector.status))}
          </span>
        </div>
      ))}
    </div>
  );
}

function displayConnectorName(name: string) {
  if (name === "direct_web") return "网页读取";
  if (name === "rss") return "RSS 新闻";
  if (name === "agent_reach") return "Agent Reach";
  return name;
}

function displayStatus(status: string) {
  if (status === "available") return "可用";
  if (status === "disabled") return "未开启";
  if (status === "unavailable") return "不可用";
  return status;
}
