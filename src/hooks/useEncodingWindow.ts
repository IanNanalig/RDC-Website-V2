import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";

export type EncodingWindowState = {
  enabled: boolean;
  start_at: string;
  end_at: string;
  is_open: boolean;
  can_encode: boolean;
  status_code: string;
  message: string;
  server_now: string;
};

const CLOSED_STATE: EncodingWindowState = {
  enabled: false,
  start_at: "",
  end_at: "",
  is_open: false,
  can_encode: false,
  status_code: "schedule_unavailable",
  message: "Contributor encoding is unavailable. Please try again later or contact the administrator.",
  server_now: "",
};

const BYPASS_STATE: EncodingWindowState = {
  ...CLOSED_STATE,
  can_encode: true,
};

const normalizeState = (raw: Partial<EncodingWindowState> | null | undefined): EncodingWindowState => ({
  enabled: Boolean(raw?.enabled),
  start_at: String(raw?.start_at || ""),
  end_at: String(raw?.end_at || ""),
  is_open: Boolean(raw?.is_open),
  can_encode: Boolean(raw?.can_encode),
  status_code: String(raw?.status_code || "schedule_unavailable"),
  message: String(raw?.message || CLOSED_STATE.message),
  server_now: String(raw?.server_now || ""),
});

export const useEncodingWindow = (shouldLoad = true) => {
  const [state, setState] = useState<EncodingWindowState>(shouldLoad ? CLOSED_STATE : BYPASS_STATE);
  const [loading, setLoading] = useState(shouldLoad);

  const refresh = useCallback(async () => {
    if (!shouldLoad) {
      setState(BYPASS_STATE);
      setLoading(false);
      return;
    }
    try {
      const data = await api.get("encoding-window/");
      setState(normalizeState(data));
    } catch (error) {
      console.error("Failed to load encoding window:", error);
      setState(CLOSED_STATE);
    } finally {
      setLoading(false);
    }
  }, [shouldLoad]);

  useEffect(() => {
    refresh();
    if (!shouldLoad) return undefined;

    const onFocus = () => refresh();
    const pollId = window.setInterval(refresh, 60_000);
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(pollId);
      window.removeEventListener("focus", onFocus);
    };
  }, [refresh, shouldLoad]);

  useEffect(() => {
    if (!shouldLoad) return undefined;
    const boundary = state.is_open ? state.end_at : state.status_code === "scheduled_not_started" ? state.start_at : "";
    if (!boundary) return undefined;
    const delay = new Date(boundary).getTime() - Date.now();
    if (!Number.isFinite(delay) || delay <= 0 || delay > 2_147_000_000) return undefined;
    const timeoutId = window.setTimeout(refresh, delay + 500);
    return () => window.clearTimeout(timeoutId);
  }, [refresh, shouldLoad, state.end_at, state.is_open, state.start_at, state.status_code]);

  return {
    ...state,
    loading,
    refresh,
  };
};

export default useEncodingWindow;
