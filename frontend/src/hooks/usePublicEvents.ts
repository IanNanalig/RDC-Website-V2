import { useEffect, useState } from "react";
import { getPublicEvents, type PublicEvent } from "../services/publicEventsApi";
import { sortEventsForDisplay } from "../utils/publicEventDisplay";

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
