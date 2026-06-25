import { getConnectors } from "@/lib/api";

export async function ConnectorStatus() {
  let connectors: Array<Record<string, unknown>> = [];
  try {
    connectors = await getConnectors();
  } catch {
    connectors = [];
  }

  if (!connectors.length) {
    return <p className="text-sm text-slate-600">Connector API is not available.</p>;
  }

  return (
    <div className="space-y-2">
      {connectors.map((connector) => (
        <div key={String(connector.name)} className="flex items-center justify-between text-sm">
          <span>{String(connector.name)}</span>
          <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-700">
            {String(connector.status)}
          </span>
        </div>
      ))}
    </div>
  );
}
