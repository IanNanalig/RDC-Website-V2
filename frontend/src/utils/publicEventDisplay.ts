import type { PublicEvent } from "../services/publicEventsApi";

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

export const sortEventsForDisplay = (events: PublicEvent[]) =>
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
