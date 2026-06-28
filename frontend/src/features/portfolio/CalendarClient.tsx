"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { createCalendarEvent, getCalendarEvents } from "@/lib/api";

export function CalendarClient({ initialEvents }: { initialEvents: Record<string, unknown> }) {
  const [events, setEvents] = useState(initialEvents);
  const [symbol, setSymbol] = useState("600519");
  const [status, setStatus] = useState<string | null>(null);

  async function addEvent() {
    await createCalendarEvent({ symbol, title: "Manual research reminder", event_date: "2026-06-28", event_type: "manual" });
    setEvents(await getCalendarEvents());
    setStatus("event added");
  }

  return (
    <div className="space-y-4">
      <div className="rounded border border-line bg-slate-50 p-3 text-sm text-slate-700">
        Calendar events are local research reminders. Future dates are shown only when already recorded.
      </div>
      <div className="flex flex-wrap gap-3">
        <input className="rounded border border-line px-3 py-2 text-sm" value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} />
        <Button onClick={addEvent}>Add Manual Event</Button>
      </div>
      {status ? <p className="text-sm text-slate-600">{status}</p> : null}
      {Array.isArray(events.events) && events.events.length ? (
        <pre className="rounded border border-line bg-white p-4 text-xs">{JSON.stringify(events, null, 2)}</pre>
      ) : (
        <p className="rounded border border-line bg-white p-3 text-sm text-slate-600">No known calendar events.</p>
      )}
    </div>
  );
}
