import { API_BASE_URL } from "../config/api";

const ACCESS_TOKEN_KEY = "accessToken";
const REFRESH_TOKEN_KEY = "refreshToken";

function getToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || null;
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || null;
}

function setAccessToken(token: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

function clearAuthStorage() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem("user");
  localStorage.removeItem("isLoggedIn");
  localStorage.removeItem("username");
}

function normalizePath(path: string) {
  const raw = path.replace(/^\//, "");
  const [base, query = ""] = raw.split("?");
  const normalizedBase = base.endsWith("/") ? base : `${base}/`;
  return query ? `${normalizedBase}?${query}` : normalizedBase;
}

function isPublicRequest(path: string, method: string) {
  const m = method.toUpperCase();
  return (
    path === "analytics/" ||
    (path === "contact/" && m === "POST") ||
    path.startsWith("public-chat/") ||
    path === "token/refresh/" ||
    (path === "access-requests/" && m === "POST") ||
    (path === "password-reset-requests/" && m === "POST") ||
    (path === "auth/login/" && m === "POST")
  );
}

function headersToRecord(headers?: HeadersInit): Record<string, string> {
  if (!headers) {
    return {};
  }
  if (headers instanceof Headers) {
    const record: Record<string, string> = {};
    headers.forEach((value, key) => {
      record[key] = value;
    });
    return record;
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return { ...headers };
}

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken() {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  const refresh = getRefreshToken();
  if (!refresh) {
    return null;
  }

  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/token/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });

      if (!res.ok) {
        return null;
      }

      const data = await res.json();
      if (!data?.access) {
        return null;
      }

      setAccessToken(data.access);
      if (data.refresh) {
        localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh);
      }
      return data.access as string;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

function redirectToLoginIfNeeded() {
  if (typeof window === "undefined") {
    return;
  }
  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

async function request(path: string, options: RequestInit = {}, hasRetried = false) {
  const method = options.method || "GET";
  const normalizedPath = normalizePath(path);
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...headersToRecord(options.headers),
  };

  const token = getToken();
  if (token && !isPublicRequest(normalizedPath, method)) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}/${normalizedPath}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && !isPublicRequest(normalizedPath, method) && !hasRetried) {
    const refreshedAccess = await refreshAccessToken();
    if (refreshedAccess) {
      return request(normalizedPath, options, true);
    }

    clearAuthStorage();
    redirectToLoginIfNeeded();
    throw new Error("Session expired. Please login again.");
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

export const api = {
  get: (path: string) => request(path, { method: "GET" }),
  post: (path: string, body?: unknown) =>
    request(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: (path: string, body?: unknown) =>
    request(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  del: (path: string) => request(path, { method: "DELETE" }),
};

export default api;
