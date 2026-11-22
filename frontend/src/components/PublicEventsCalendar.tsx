import { useId, useMemo, useState } from "react";
import { usePublicEvents } from "../hooks/usePublicEvents";
import { eventPillTone, eventTone, getEventTiming } from "../utils/publicEventDisplay";

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
