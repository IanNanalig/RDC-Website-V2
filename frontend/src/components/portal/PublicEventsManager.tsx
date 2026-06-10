import React, { useCallback, useEffect, useState } from "react";
import { api } from "../../services/api";

type PublicEventRow = {
  id: number;
  title: string;
  description: string;
  event_type: string;
  start_at: string;
  end_at?: string;
  location: string;
  is_virtual: boolean;
  meeting_link: string;
  status: "draft" | "submitted" | "published" | "rejected" | "archived";
  review_notes?: string;
  published_at?: string;
  updated_at: string;
};

type PublicEventForm = {
  id?: number;
  title: string;
  description: string;
  event_type: string;
  start_at: string;
  end_at: string;
  location: string;
  is_virtual: boolean;
  meeting_link: string;
};

type Props = {
  mode: "admin" | "editor";
  onChanged?: () => void;
};

const emptyEventForm: PublicEventForm = {
  title: "",
  description: "",
  event_type: "meeting",
  start_at: "",
  end_at: "",
  location: "",
  is_virtual: false,
  meeting_link: "",
};

const getErrorDetail = (err: unknown, fallback: string) => {
  if (err instanceof Error && err.message) {
    try {
      const parsed = JSON.parse(err.message);
      return parsed?.detail || fallback;
    } catch {
      return err.message;
    }
  }
  return fallback;
};

const toDateTimeLocal = (value?: string) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 16);
};

const statusClass = (status: PublicEventRow["status"]) => {
  if (status === "published") return "bg-emerald-100 text-emerald-700";
  if (status === "submitted") return "bg-blue-100 text-blue-700";
  if (status === "rejected") return "bg-rose-100 text-rose-700";
  if (status === "archived") return "bg-slate-200 text-slate-700";
  return "bg-amber-100 text-amber-700";
};

const PublicEventsManager: React.FC<Props> = ({ mode, onChanged }) => {
  const [events, setEvents] = useState<PublicEventRow[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventForm, setEventForm] = useState<PublicEventForm>(emptyEventForm);
  const [notice, setNotice] = useState("");

  const isAdmin = mode === "admin";

  const loadEvents = useCallback(async () => {
    setEventsLoading(true);
    try {
      const data = await api.get("admin/events/");
      setEvents(Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : []);
    } catch (error) {
      console.error(error);
      setEvents([]);
      setNotice(getErrorDetail(error, "Failed to load events."));
    } finally {
      setEventsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const editEvent = (event: PublicEventRow) => {
    setEventForm({
      id: event.id,
      title: event.title || "",
      description: event.description || "",
      event_type: event.event_type || "meeting",
      start_at: toDateTimeLocal(event.start_at),
      end_at: toDateTimeLocal(event.end_at),
      location: event.location || "",
      is_virtual: Boolean(event.is_virtual),
      meeting_link: event.meeting_link || "",
    });
  };

  const saveEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice("");
    if (!eventForm.title.trim() || !eventForm.start_at) {
      setNotice("Event title and start date/time are required.");
      return;
    }
    try {
      const payload = {
        title: eventForm.title.trim(),
        description: eventForm.description.trim(),
        event_type: eventForm.event_type,
        start_at: eventForm.start_at,
        end_at: eventForm.end_at || null,
        location: eventForm.location.trim(),
        is_virtual: eventForm.is_virtual,
        meeting_link: eventForm.meeting_link.trim(),
      };
      if (eventForm.id) {
        await api.put(`admin/events/${eventForm.id}/`, payload);
        setNotice("Event draft updated.");
      } else {
        await api.post("admin/events/", payload);
        setNotice("Event draft created.");
      }
      setEventForm(emptyEventForm);
      await loadEvents();
      onChanged?.();
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to save event."));
    }
  };

  const runEventAction = async (
    event: PublicEventRow,
    action: "submit" | "publish" | "reject" | "archive",
  ) => {
    setNotice("");
    try {
      await api.post(`admin/events/${event.id}/${action}/`, {});
      const labels: Record<typeof action, string> = {
        submit: "Event submitted for admin review.",
        publish: "Event published to the public website.",
        reject: "Event rejected.",
        archive: "Event archived.",
      };
      setNotice(labels[action]);
      await loadEvents();
      onChanged?.();
    } catch (error) {
      setNotice(getErrorDetail(error, `Failed to ${action} event.`));
    }
  };

  return (
    <div className="portal-card">
      <div className="portal-card-header flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Public Events Calendar</h2>
          <p className="text-xs text-slate-500">
            {isAdmin
              ? "Review, publish, reject, and archive Home page events."
              : "Create event drafts and submit them for administrator publishing."}
          </p>
        </div>
        <button type="button" onClick={loadEvents} className="portal-btn portal-btn-ghost">
          Refresh Events
        </button>
      </div>

      {notice && (
        <div className="mx-4 mt-4 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
          {notice}
        </div>
      )}

      <form onSubmit={saveEvent} className="portal-card-body border-b border-slate-200">
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <label className="block">
            <span className="text-sm text-slate-700">Event Title *</span>
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={eventForm.title}
              onChange={(e) => setEventForm((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="RDC Full Council Meeting"
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Event Type</span>
            <select
              className="mt-1 w-full rounded-lg border bg-white px-3 py-2"
              value={eventForm.event_type}
              onChange={(e) => setEventForm((prev) => ({ ...prev, event_type: e.target.value }))}
            >
              <option value="meeting">Meeting</option>
              <option value="forum">Forum</option>
              <option value="consultation">Consultation</option>
              <option value="deadline">Deadline</option>
              <option value="summit">Summit</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Start Date and Time *</span>
            <input
              type="datetime-local"
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={eventForm.start_at}
              onChange={(e) => setEventForm((prev) => ({ ...prev, start_at: e.target.value }))}
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">End Date and Time</span>
            <input
              type="datetime-local"
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={eventForm.end_at}
              onChange={(e) => setEventForm((prev) => ({ ...prev, end_at: e.target.value }))}
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Location / Venue</span>
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={eventForm.location}
              onChange={(e) => setEventForm((prev) => ({ ...prev, location: e.target.value }))}
              placeholder="MMDA Building or Virtual"
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Meeting Link</span>
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={eventForm.meeting_link}
              onChange={(e) => setEventForm((prev) => ({ ...prev, meeting_link: e.target.value }))}
              placeholder="https://..."
            />
          </label>
          <label className="flex items-center gap-2 xl:col-span-2">
            <input
              type="checkbox"
              checked={eventForm.is_virtual}
              onChange={(e) => setEventForm((prev) => ({ ...prev, is_virtual: e.target.checked }))}
            />
            <span className="text-sm text-slate-700">This is a virtual or online event.</span>
          </label>
          <label className="block xl:col-span-2">
            <span className="text-sm text-slate-700">Public Description</span>
            <textarea
              className="mt-1 min-h-[90px] w-full rounded-lg border px-3 py-2"
              value={eventForm.description}
              onChange={(e) => setEventForm((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="Brief public-facing details, agenda note, or participation instructions."
            />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="submit" className="portal-btn portal-btn-primary">
            {eventForm.id ? "Save Event Draft" : "Create Event Draft"}
          </button>
          {eventForm.id && (
            <button type="button" onClick={() => setEventForm(emptyEventForm)} className="portal-btn portal-btn-ghost">
              Cancel Edit
            </button>
          )}
        </div>
      </form>

      <div className="portal-card-body">
        {eventsLoading ? (
          <p className="text-sm text-slate-500">Loading public events...</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-slate-500">No events created yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {events.map((event) => {
              const editorCanEdit = event.status === "draft" || event.status === "rejected";
              return (
                <div key={event.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(event.status)}`}>
                          {event.status}
                        </span>
                        <span className="rounded-full bg-purple-100 px-2 py-1 text-xs font-semibold text-purple-700">
                          {event.event_type}
                        </span>
                      </div>
                      <h3 className="mt-2 font-semibold text-slate-900">{event.title}</h3>
                      <p className="mt-1 text-sm text-slate-600">
                        {event.start_at
                          ? new Date(event.start_at).toLocaleString("en-PH", { timeZone: "Asia/Manila" })
                          : "No date"}
                      </p>
                      <p className="mt-1 text-sm text-slate-500">
                        {event.location || (event.is_virtual ? "Virtual" : "Location not set")}
                      </p>
                    </div>
                    {(isAdmin || editorCanEdit) && (
                      <button type="button" onClick={() => editEvent(event)} className="portal-btn portal-btn-ghost w-fit">
                        Edit
                      </button>
                    )}
                  </div>
                  {event.description && <p className="mt-3 line-clamp-2 text-sm text-slate-600">{event.description}</p>}
                  <div className="mt-4 flex flex-wrap gap-2">
                    {!isAdmin && editorCanEdit && (
                      <button
                        type="button"
                        onClick={() => runEventAction(event, "submit")}
                        className="text-sm font-semibold text-blue-600 hover:underline"
                      >
                        Submit for Review
                      </button>
                    )}
                    {isAdmin && event.status !== "published" && event.status !== "archived" && (
                      <button
                        type="button"
                        onClick={() => runEventAction(event, "publish")}
                        className="text-sm font-semibold text-emerald-600 hover:underline"
                      >
                        Publish
                      </button>
                    )}
                    {isAdmin && (event.status === "submitted" || event.status === "draft") && (
                      <button
                        type="button"
                        onClick={() => runEventAction(event, "reject")}
                        className="text-sm font-semibold text-rose-600 hover:underline"
                      >
                        Reject
                      </button>
                    )}
                    {isAdmin && event.status !== "archived" && (
                      <button
                        type="button"
                        onClick={() => runEventAction(event, "archive")}
                        className="text-sm font-semibold text-slate-500 hover:underline"
                      >
                        Archive
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default PublicEventsManager;
