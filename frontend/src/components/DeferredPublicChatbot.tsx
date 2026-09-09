import React, { lazy, Suspense, useState } from "react";

const PublicChatbot = lazy(() => import("./PublicChatbot"));

const Launcher = ({ onClick, loading = false }: { onClick: () => void; loading?: boolean }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={loading}
    className="fixed bottom-6 right-6 z-40 flex items-center gap-3 rounded-full bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 px-5 py-3 font-semibold text-white shadow-2xl transition hover:scale-[1.02] hover:shadow-emerald-200 disabled:opacity-80"
    aria-label="Open chatbot"
    title="Ask the RDC-NCR public site assistant"
  >
    <span className="relative flex h-3 w-3">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-60" />
      <span className="relative inline-flex h-3 w-3 rounded-full bg-white" />
    </span>
    <span className="hidden sm:inline">{loading ? "Opening..." : "Ask RDC Assistant"}</span>
    <span className="sm:hidden">Ask</span>
  </button>
);

const DeferredPublicChatbot: React.FC = () => {
  const [activated, setActivated] = useState(false);
  if (!activated) return <Launcher onClick={() => setActivated(true)} />;
  return (
    <Suspense fallback={<Launcher loading onClick={() => undefined} />}>
      <PublicChatbot initiallyOpen />
    </Suspense>
  );
};

export default DeferredPublicChatbot;
