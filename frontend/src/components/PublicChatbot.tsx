import React, { useEffect, useRef, useState } from "react";
import { api } from "../services/api";

type SourceLink = { title: string; url: string };
type AnswerType = "direct" | "related" | "fallback" | "blocked";
type FeedbackValue = "up" | "down";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  answerType?: AnswerType;
  confidence?: number;
  interactionId?: number;
  sources?: SourceLink[];
  relatedLinks?: SourceLink[];
  feedback?: FeedbackValue;
};

const DEFAULT_BANNER = "I answer questions about the RDC-NCR public website and public dashboard only.";

const quickActions = [
  { label: "Documents", question: "Where can I download RDIP documents?" },
  { label: "Projects Dashboard", question: "How many projects are in the public dashboard?" },
  { label: "RDC Office", question: "Where is the RDC-NCR office located?" },
  { label: "News", question: "Where can I read RDC-NCR news?" },
  { label: "Regional Profile", question: "What can I find in the Regional Profile page?" },
];

const typeMeta: Record<AnswerType, { label: string; className: string }> = {
  direct: { label: "Verified answer", className: "bg-emerald-100 text-emerald-700" },
  related: { label: "Possible match", className: "bg-amber-100 text-amber-700" },
  fallback: { label: "Needs clarification", className: "bg-slate-200 text-slate-700" },
  blocked: { label: "Safety notice", className: "bg-rose-100 text-rose-700" },
};

const makeId = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`;

const PublicChatbot: React.FC = () => {
  const isDashboardPage =
    typeof window !== "undefined" && window.location.pathname.toLowerCase().startsWith("/projects");
  const panelPositionClass = isDashboardPage ? "sm:bottom-6 sm:right-6 sm:w-[360px]" : "sm:bottom-6 sm:right-6 sm:w-[440px]";
  const panelMaxWidthClass = isDashboardPage ? "max-w-[380px]" : "max-w-[460px]";
  const panelBodyClass = isDashboardPage ? "max-h-[50vh] sm:max-h-[54vh]" : "max-h-[58vh] sm:max-h-[62vh]";
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggested, setSuggested] = useState<string[]>([]);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const loadSuggestions = async () => {
      try {
        const data = await api.get("public-chat/faq/");
        if (Array.isArray(data?.questions)) {
          setSuggested(data.questions);
        }
      } catch {
        // Public assistant should never break the website.
      }
    };
    loadSuggestions();
  }, [open]);

  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, loading]);

  const submitQuestion = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    const userMessage: ChatMessage = { id: makeId(), role: "user", text: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    try {
      const response = await api.post("public-chat/ask/", { question: trimmed });
      const assistant: ChatMessage = {
        id: makeId(),
        role: "assistant",
        text: response?.answer || "Sorry, I could not find an answer.",
        answerType: response?.answer_type || "fallback",
        confidence: Number(response?.confidence || 0),
        interactionId: response?.interaction_id,
        sources: Array.isArray(response?.sources) ? response.sources : [],
        relatedLinks: Array.isArray(response?.related_links) ? response.related_links : [],
      };
      setMessages((prev) => [...prev, assistant]);
      if (Array.isArray(response?.suggested_questions)) {
        setSuggested(response.suggested_questions);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: makeId(),
          role: "assistant",
          text: "Sorry, I could not process that request. Please try again or use the Contact page for a specific inquiry.",
          answerType: "fallback",
          confidence: 0,
          sources: [{ title: "Contact", url: "/contact" }],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const sendFeedback = async (messageId: string, interactionId: number | undefined, feedback: FeedbackValue) => {
    setMessages((prev) => prev.map((msg) => (msg.id === messageId ? { ...msg, feedback } : msg)));
    if (!interactionId) return;
    try {
      await api.post("public-chat/feedback/", { interaction_id: interactionId, feedback });
    } catch {
      // Feedback is helpful but non-critical.
    }
  };

  const renderLinks = (title: string, links?: SourceLink[]) => {
    if (!links || links.length === 0) return null;
    return (
      <div className="mt-3">
        <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}</div>
        <div className="flex flex-wrap gap-1.5">
          {links.map((src) => (
            <a
              key={`${title}-${src.url}-${src.title}`}
              href={src.url}
              target={src.url.startsWith("http") || src.url.startsWith("mailto:") ? "_blank" : undefined}
              rel={src.url.startsWith("http") ? "noopener noreferrer" : undefined}
              className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-100 hover:bg-emerald-50"
            >
              {src.title}
            </a>
          ))}
        </div>
      </div>
    );
  };

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-3 rounded-full bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 px-5 py-3 font-semibold text-white shadow-2xl transition hover:scale-[1.02] hover:shadow-emerald-200"
          aria-label="Open chatbot"
          title="Ask the RDC-NCR public site assistant"
        >
          <span className="relative flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-60" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-white" />
          </span>
          <span className="hidden sm:inline">Ask RDC Assistant</span>
          <span className="sm:hidden">Ask</span>
        </button>
      )}

      {open && (
        <div className={`fixed inset-x-3 bottom-3 z-50 mx-auto w-auto ${panelMaxWidthClass} sm:inset-x-auto ${panelPositionClass}`}>
          <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
            <div className="bg-gradient-to-r from-emerald-800 via-teal-800 to-cyan-800 px-5 py-4 text-white">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs uppercase tracking-[0.22em] text-emerald-100">RDC Public Assistant</div>
                  <div className="text-lg font-bold">How can I help today?</div>
                  <div className="mt-1 text-xs text-emerald-50">{DEFAULT_BANNER}</div>
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded-full bg-white/10 p-2 transition hover:bg-white/20"
                  aria-label="Close chatbot"
                >
                  <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            <div ref={listRef} className={`${panelBodyClass} overflow-y-auto bg-slate-50 px-4 py-4`}>
              {messages.length === 0 && (
                <div className="space-y-4">
                  <div className="rounded-2xl bg-white p-4 text-sm text-slate-700 shadow-sm ring-1 ring-slate-100">
                    Ask in English, Tagalog, or Taglish. I can help with public pages, documents, dashboard data, contact details, and navigation.
                  </div>
                  <div className={`grid grid-cols-1 gap-2 ${isDashboardPage ? "" : "sm:grid-cols-2"}`}>
                    {quickActions.map((action) => (
                      <button
                        key={action.label}
                        type="button"
                        onClick={() => submitQuestion(action.question)}
                        className="rounded-2xl border border-emerald-100 bg-white p-3 text-left text-sm font-semibold text-slate-800 shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-md"
                      >
                        <span className="block text-emerald-600">{action.label}</span>
                        <span className="mt-1 block text-xs font-normal text-slate-500">{action.question}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-4">
                {messages.map((msg) => {
                  const meta = msg.answerType ? typeMeta[msg.answerType] : null;
                  return (
                    <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                      <div
                        className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                          msg.role === "user"
                            ? "bg-emerald-600 text-white"
                            : "bg-white text-slate-900 ring-1 ring-slate-100"
                        }`}
                      >
                        {meta && (
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${meta.className}`}>
                              {meta.label}
                            </span>
                            {typeof msg.confidence === "number" && (
                              <span className="text-[11px] text-slate-500">
                                confidence {Math.round(msg.confidence * 100)}%
                              </span>
                            )}
                          </div>
                        )}
                        <p className="whitespace-pre-wrap">{msg.text}</p>
                        {renderLinks("Sources", msg.sources)}
                        {renderLinks("Related links", msg.relatedLinks)}
                        {msg.role === "assistant" && (
                          <div className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-2 text-xs text-slate-500">
                            <span>Was this helpful?</span>
                            <button
                              type="button"
                              onClick={() => sendFeedback(msg.id, msg.interactionId, "up")}
                              className={`rounded-full px-2 py-1 ${msg.feedback === "up" ? "bg-emerald-100 text-emerald-700" : "hover:bg-slate-100"}`}
                            >
                              Yes
                            </button>
                            <button
                              type="button"
                              onClick={() => sendFeedback(msg.id, msg.interactionId, "down")}
                              className={`rounded-full px-2 py-1 ${msg.feedback === "down" ? "bg-rose-100 text-rose-700" : "hover:bg-slate-100"}`}
                            >
                              No
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
                {loading && (
                  <div className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-2 text-xs text-slate-500 shadow-sm ring-1 ring-slate-100">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
                    Thinking through the public knowledge base...
                  </div>
                )}
              </div>
            </div>

            <div className="border-t bg-white px-4 py-3">
              {suggested.length > 0 && (
                <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
                  {suggested.slice(0, 5).map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => submitQuestion(q)}
                      className="shrink-0 rounded-full bg-slate-100 px-3 py-1.5 text-xs text-slate-700 transition hover:bg-emerald-50 hover:text-emerald-700"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  submitQuestion(input);
                }}
                className="flex items-center gap-2"
              >
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about pages, documents, dashboard data..."
                  className="min-w-0 flex-1 rounded-full border border-slate-200 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <button
                  type="submit"
                  className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-50"
                  disabled={loading}
                >
                  Send
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default PublicChatbot;
