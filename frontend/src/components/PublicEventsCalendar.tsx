import { useEffect, useId, useMemo, useState } from "react";
import { getPublicEvents, type PublicEvent } from "../services/publicEventsApi";

const EVENT_TIME_ZONE = "Asia/Manila";

const eventDayKey = (date: Date) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: EVENT_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);

const formatEventMoment = (date: Date, now: Date) => {
  const time = date.toLocaleTimeString("en-US", {
    timeZone: EVENT_TIME_ZONE,
    hour: "numeric",
    minute: "2-digit",
  });
  const todayKey = eventDayKey(now);
  const dateKey = eventDayKey(date);
  const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);

  if (dateKey === todayKey) return `today at ${time}`;
  if (dateKey === eventDayKey(tomorrow)) return `tomorrow at ${time}`;

  const day = date.toLocaleDateString("en-US", {
    timeZone: EVENT_TIME_ZONE,
    month: "short",
    day: "numeric",
    year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
  return `${day} at ${time}`;
};

const formatTimeRemaining = (milliseconds: number) => {
  const totalMinutes = Math.max(1, Math.ceil(milliseconds / 60_000));
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) {
    return `${days} day${days === 1 ? "" : "s"}${hours ? ` ${hours} hr` : ""}`;
  }
  if (hours > 0) {
    return `${hours} hr${minutes ? ` ${minutes} min` : ""}`;
  }
  return `${minutes} min`;
};

export const getEventTiming = (event: PublicEvent) => {
  const start = new Date(event.start_at);
  const end = event.end_at
    ? new Date(event.end_at)
    : new Date(start.getTime() + 2 * 60 * 60 * 1000);
  const now = new Date();

  if (Number.isNaN(start.getTime())) {
    return {
      rank: 1,
      label: "Scheduled",
      message: "This event is scheduled.",
      className: "bg-blue-50 text-blue-700 ring-1 ring-blue-100",
      messageClassName: "border-blue-100 bg-blue-50 text-blue-700",
    };
  }

  if (now >= start && now < end) {
    return {
      rank: 0,
      label: "Happening now",
      message: `Ends ${formatEventMoment(end, now)} · ${formatTimeRemaining(end.getTime() - now.getTime())} remaining.`,
      className: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
      messageClassName: "border-emerald-100 bg-emerald-50 text-emerald-800",
    };
  }

  if (now >= end) {
    return {
      rank: 2,
      label: "Ended",
      message: `Ended ${formatEventMoment(end, now)}.`,
      className: "bg-slate-100 text-slate-600 ring-1 ring-slate-200",
      messageClassName: "border-slate-200 bg-slate-50 text-slate-600",
    };
  }

  return {
    rank: 1,
    label: "Upcoming",
    message: `Starts ${formatEventMoment(start, now)} · Ends ${formatEventMoment(end, now)}.`,
    className: "bg-blue-50 text-blue-700 ring-1 ring-blue-100",
    messageClassName: "border-blue-100 bg-blue-50 text-blue-700",
  };
};

const sortEventsForDisplay = (events: PublicEvent[]) =>
  [...events].sort((a, b) => {
    const aTiming = getEventTiming(a);
    const bTiming = getEventTiming(b);
    if (aTiming.rank !== bTiming.rank) return aTiming.rank - bTiming.rank;
    const aStart = new Date(a.start_at).getTime() || 0;
    const bStart = new Date(b.start_at).getTime() || 0;
    if (aTiming.rank === 2) return bStart - aStart;
    return aStart - bStart;
  });

export const eventTone = (type: string) => {
  if (type === "meeting") return "bg-blue-100 text-blue-700";
  if (type === "forum" || type === "consultation")
    return "bg-green-100 text-green-700";
  if (type === "deadline") return "bg-amber-100 text-amber-700";
  return "bg-purple-100 text-purple-700";
};

export const eventPillTone = (type: string) => {
  if (type === "meeting") return "bg-blue-50 text-blue-600";
  if (type === "forum" || type === "consultation")
    return "bg-green-50 text-green-600";
  if (type === "deadline") return "bg-amber-50 text-amber-700";
  return "bg-purple-50 text-purple-600";
};

export function usePublicEvents(enabled = true) {
  const [calendarEvents, setCalendarEvents] = useState<PublicEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState("");

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    getPublicEvents({ limit: 50, includePast: true })
      .then((events) => { if (!cancelled) setCalendarEvents(sortEventsForDisplay(events)); })
      .catch(() => { if (!cancelled) setEventsError("Events calendar is temporarily unavailable."); })
      .finally(() => { if (!cancelled) setEventsLoading(false); });
    return () => { cancelled = true; };
  }, [enabled]);

  return { calendarEvents, eventsLoading, eventsError };
}

export function PublicEventsCalendarContent({
  calendarEvents, eventsLoading, eventsError,
}: ReturnType<typeof usePublicEvents>) {
  const filterId = useId();
  const [calendarFilter, setCalendarFilter] = useState("all");
  const filteredCalendarEvents = useMemo(
    () =>
      calendarEvents.filter((event) =>
        calendarFilter === "all" ? true : event.event_type === calendarFilter,
      ),
    [calendarEvents, calendarFilter],
  );

  return (
    <>
      <div className="border-b border-slate-200 bg-white px-5 py-4">
        <label htmlFor={filterId} className="block text-sm font-semibold text-slate-700">
          Filter by event type
        </label>
        <select
          id={filterId}
          value={calendarFilter}
          onChange={(event) => setCalendarFilter(event.target.value)}
          className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm sm:max-w-xs"
        >
          <option value="all">All events</option>
          <option value="meeting">Meetings</option>
          <option value="forum">Forums</option>
          <option value="consultation">Consultations</option>
          <option value="deadline">Deadlines</option>
          <option value="summit">Summits</option>
          <option value="other">Other</option>
        </select>
      </div>
      <div className="bg-slate-50 p-5">
        {eventsLoading ? <p role="status">Loading events...</p> : eventsError ? <p role="alert">{eventsError}</p> : filteredCalendarEvents.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-600">
            No events match this filter.
          </div>
        ) : (
          <div className="grid gap-4">
            {filteredCalendarEvents.map((event) => {
              const timing = getEventTiming(event);
              return (
                <article
                  key={event.id}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                    <div
                      className={`${eventTone(event.event_type)} rounded-2xl px-4 py-3 text-center sm:w-24`}
                    >
                      <div className="text-2xl font-black">
                        {event.day}
                      </div>
                      <div className="text-xs font-bold uppercase tracking-wide">
                        {event.month}
                      </div>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${eventPillTone(event.event_type)}`}
                        >
                          {event.event_type}
                        </span>
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${timing.className}`}
                        >
                          {timing.label}
                        </span>
                        <span className="text-xs text-slate-500">
                          {event.time}
                          {event.end_time ? ` - ${event.end_time}` : ""}
                        </span>
                      </div>
                      <h3 className="mt-2 text-lg font-black text-slate-900">
                        {event.title}
                      </h3>
                      <p className="mt-1 text-sm font-medium text-slate-600">
                        {event.location ||
                          (event.is_virtual
                            ? "Virtual event"
                            : "Location to be announced")}
                      </p>
                      <p
                        className={`mt-3 rounded-lg border px-3 py-2 text-sm font-semibold ${timing.messageClassName || "border-slate-200 bg-slate-50 text-slate-600"}`}
                      >
                        {timing.message}
                      </p>
                      {event.description && (
                        <p className="mt-3 text-sm leading-6 text-slate-600">
                          {event.description}
                        </p>
                      )}
                      {/^https?:\/\//i.test(event.meeting_link || "") && (
                        <a
                          href={event.meeting_link}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-3 inline-flex rounded-full bg-purple-600 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-700"
                        >
                          Open event link
                        </a>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

export default function PublicEventsCalendar() {
  const events = usePublicEvents();
  return (
    <section id="events" aria-labelledby="events-heading" className="mt-12 scroll-mt-28 overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <h2 id="events-heading" className="border-b border-slate-200 px-5 py-5 text-2xl font-bold text-slate-900">RDC-NCR Events Calendar</h2>
      <PublicEventsCalendarContent {...events} />
    </section>
  );
}
