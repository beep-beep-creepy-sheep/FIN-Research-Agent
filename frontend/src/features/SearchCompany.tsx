"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

export function SearchCompany() {
  const [symbol, setSymbol] = useState("600519");

  return (
    <form
      className="flex gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        window.location.href = `/companies/${encodeURIComponent(symbol)}`;
      }}
    >
      <Input value={symbol} onChange={(event) => setSymbol(event.target.value.trim())} placeholder="例如 600519" />
      <Button type="submit">打开</Button>
    </form>
  );
}
