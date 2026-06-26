"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { uploadDocument } from "@/lib/api";

export function DocumentUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [issuer, setIssuer] = useState("600519");
  const [reportPeriod, setReportPeriod] = useState("");
  const [publicationDate, setPublicationDate] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setMessage("先选择一个 PDF、Markdown、TXT、CSV 或 JSON 文件。");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("issuer", issuer);
      form.append("report_period", reportPeriod);
      form.append("publication_date", publicationDate);
      const result = await uploadDocument(form);
      setMessage(`已导入文档 #${String(result.id ?? "")}，刷新公司页后可作为证据检索。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="space-y-3" onSubmit={submit}>
      <Input
        type="file"
        accept=".pdf,.txt,.md,.csv,.json"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
      />
      <div className="grid gap-2 sm:grid-cols-3">
        <Input value={issuer} onChange={(event) => setIssuer(event.target.value.trim())} placeholder="公司代码" />
        <Input value={reportPeriod} onChange={(event) => setReportPeriod(event.target.value)} placeholder="报告期 2025" />
        <Input
          value={publicationDate}
          onChange={(event) => setPublicationDate(event.target.value)}
          placeholder="发布日期 YYYY-MM-DD"
        />
      </div>
      <Button type="submit" disabled={busy}>{busy ? "导入中..." : "导入证据文档"}</Button>
      <p className="text-xs text-slate-500">
        PDF 会保存到本地 `data/documents` 并写入 Postgres；相同文件会更新，不会重复入库。
      </p>
      {message ? <p className="text-sm text-slate-600">{message}</p> : null}
    </form>
  );
}
