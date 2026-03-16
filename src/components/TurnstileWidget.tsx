import React, { useEffect, useRef } from "react";

declare global {
  interface Window {
    turnstile?: {
      render: (element: HTMLElement, options: Record<string, any>) => string | number;
      remove: (widgetId: string | number) => void;
    };
  }
}

type TurnstileWidgetProps = {
  onToken: (token: string) => void;
};

const siteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY as string | undefined;

const TurnstileWidget: React.FC<TurnstileWidgetProps> = ({ onToken }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetId = useRef<string | number | null>(null);

  useEffect(() => {
    if (!siteKey || !containerRef.current) return;
    let cancelled = false;

    const renderWidget = () => {
      if (!containerRef.current || !window.turnstile) return;
      if (widgetId.current) {
        window.turnstile.remove(widgetId.current);
      }
      widgetId.current = window.turnstile.render(containerRef.current, {
        sitekey: siteKey,
        callback: (token: string) => {
          if (!cancelled) onToken(token);
        },
        "expired-callback": () => {
          if (!cancelled) onToken("");
        },
      });
    };

    const existingScript = document.querySelector("script[data-turnstile]");
    if (!existingScript) {
      const script = document.createElement("script");
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      script.defer = true;
      script.setAttribute("data-turnstile", "true");
      script.onload = () => {
        if (!cancelled) renderWidget();
      };
      document.head.appendChild(script);
    } else {
      renderWidget();
    }

    return () => {
      cancelled = true;
      if (widgetId.current && window.turnstile) {
        window.turnstile.remove(widgetId.current);
      }
    };
  }, [onToken]);

  if (!siteKey) return null;
  return <div ref={containerRef} />;
};

export default TurnstileWidget;
