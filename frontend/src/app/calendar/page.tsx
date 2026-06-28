import { Card } from "@/components/Card";
import { CalendarClient } from "@/features/portfolio/CalendarClient";
import { getCalendarEvents } from "@/lib/api";

export default async function CalendarPage() {
  let events: Record<string, unknown> = { events: [], state: "no_known_events" };
  try {
    events = await getCalendarEvents();
  } catch {
    events = { events: [], state: "api_unavailable" };
  }
  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6">
        <p className="text-sm font-medium text-accent">Local calendar</p>
        <h1 className="mt-1 text-3xl font-semibold">Research Calendar</h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          Filing, report, alert, and manual research events from the local database. Future events are never guessed.
        </p>
      </div>
      <Card title="Calendar Events">
        <CalendarClient initialEvents={events} />
      </Card>
    </main>
  );
}
