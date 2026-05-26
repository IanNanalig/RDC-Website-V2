import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";

// Initialize Sentry if configured at build time
if (import.meta.env.VITE_SENTRY_DSN) {
  // Dynamically import to avoid adding overhead when not used
  import("@sentry/react").then((Sentry) => {
    import("@sentry/tracing").then(() => {
      Sentry.init({
        dsn: import.meta.env.VITE_SENTRY_DSN,
        integrations: [new Sentry.BrowserTracing()],
        tracesSampleRate: Number(
          import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || 0.0,
        ),
      });
    });
  });
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
