import React, { useEffect, useRef, useState } from "react";
import { api } from "../services/api";

type SourceLink = { title: string; url: string };
type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  sources?: SourceLink[];
};

const DEFAULT_BANNER =
  "I answer questions about the RDC-NCR public site only.";

const PublicChatbot: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggested, setSuggested] = useState<string[]>([]);
  const [banner] = useState(DEFAULT_BANNER);
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
        // silent for public UI
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
    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setInput("");
    setLoading(true);
    try {
      const response = await api.post("public-chat/ask/", { question: trimmed });
      const assistant: ChatMessage = {
        role: "assistant",
        text: response?.answer || "Sorry, I could not find an answer.",
        sources: response?.sources || [],
      };
      setMessages((prev) => [...prev, assistant]);
      if (Array.isArray(response?.suggested_questions)) {
        setSuggested(response.suggested_questions);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Sorry, I could not process that request. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-3 px-5 py-3 rounded-full bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 text-white font-semibold shadow-2xl hover:shadow-3xl transition"
          aria-label="Open chatbot"
          title="Ask the RDC-NCR public site assistant"
        >
          <span className="w-2.5 h-2.5 rounded-full bg-white animate-pulse" />
          <span className="hidden sm:inline">Ask RDC Assistant</span>
          <span className="sm:hidden">Ask</span>
        </button>
      )}

      {open && (
        <div className="fixed bottom-6 right-6 z-50 w-[92vw] max-w-[420px]">
          <div className="rounded-3xl shadow-2xl border border-slate-200 bg-white overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-emerald-700 via-teal-700 to-cyan-700 text-white">
              <div>
                <div className="text-sm uppercase tracking-wide opacity-80">
                  RDC Public Assistant
                </div>
                <div className="text-lg font-semibold">
                  Ask about the public website
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-2 rounded-full bg-white/10 hover:bg-white/20 transition"
                aria-label="Close chatbot"
              >
                <svg
                  className="w-5 h-5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="px-5 py-3 text-xs text-slate-600 bg-slate-50 border-b">
              {banner}
            </div>

            <div
              ref={listRef}
              className="max-h-[50vh] overflow-y-auto px-5 py-4 space-y-4 bg-white"
            >
              {messages.length === 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-slate-600">
                    Start by asking about RDC-NCR documents, news, projects,
                    or the regional profile.
                  </p>
                  {suggested.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {suggested.map((q) => (
                        <button
                          key={q}
                          type="button"
                          onClick={() => submitQuestion(q)}
                          className="px-3 py-1.5 rounded-full text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {messages.map((msg, idx) => (
                <div
                  key={`${msg.role}-${idx}`}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-emerald-600 text-white"
                        : "bg-slate-100 text-slate-900"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.text}</p>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-3 space-y-1 text-xs text-slate-600">
                        <div className="font-semibold">Sources</div>
                        {msg.sources.map((src) => (
                          <a
                            key={src.url}
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block text-emerald-700 hover:underline"
                          >
                            {src.title}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="text-xs text-slate-500">Thinking...</div>
              )}
            </div>

            <div className="border-t bg-white px-4 py-3">
              {suggested.length > 0 && messages.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {suggested.slice(0, 4).map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => submitQuestion(q)}
                      className="px-3 py-1.5 rounded-full text-xs bg-slate-100 text-slate-700 hover:bg-slate-200 transition"
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
                  placeholder="Ask about RDC-NCR documents or pages..."
                  className="flex-1 rounded-full border border-slate-200 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <button
                  type="submit"
                  className="px-4 py-2 rounded-full bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 transition"
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
