import { API_BASE_URL } from "../config/api";

const ACCESS_TOKEN_KEY = "accessToken";
const REFRESH_TOKEN_KEY = "refreshToken";
const SESSION_MESSAGE_KEY = "sessionMessage";
const DEFAULT_SESSION_EXPIRED_MESSAGE = "Session expired. Please login again.";
const SESSION_REPLACED_MESSAGE =
  "Your account was signed in from another browser or device. Please login again.";

function getToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || null;
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || null;
}

function setAccessToken(token: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

function clearAuthStorage(message?: string) {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem("user");
  localStorage.removeItem("isLoggedIn");
  localStorage.removeItem("username");
  if (message) {
    localStorage.setItem(SESSION_MESSAGE_KEY, message);
  }
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
    path.startsWith("public/projects/") ||
    path.startsWith("public/events/") ||
    path.startsWith("public/cms/") ||
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
let lastAuthFailureMessage = "";

async function errorMessageFromResponse(res: Response) {
  try {
    const data = await res.clone().json();
    const detail = String(data?.detail || "");
    if (detail.toLowerCase().includes("another browser") || detail.toLowerCase().includes("another device")) {
      return SESSION_REPLACED_MESSAGE;
    }
    return detail || DEFAULT_SESSION_EXPIRED_MESSAGE;
  } catch {
    return DEFAULT_SESSION_EXPIRED_MESSAGE;
  }
}

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
        lastAuthFailureMessage = await errorMessageFromResponse(res);
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
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: Record<string, string> = isFormData
    ? headersToRecord(options.headers)
    : {
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
    const unauthorizedMessage = await errorMessageFromResponse(res);
    const refreshedAccess = await refreshAccessToken();
    if (refreshedAccess) {
      return request(normalizedPath, options, true);
    }

    const message = lastAuthFailureMessage || unauthorizedMessage || DEFAULT_SESSION_EXPIRED_MESSAGE;
    lastAuthFailureMessage = "";
    clearAuthStorage(message);
    redirectToLoginIfNeeded();
    throw new Error(message);
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
  postForm: (path: string, body: FormData) =>
    request(path, { method: "POST", body }),
  put: (path: string, body?: unknown) =>
    request(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  putForm: (path: string, body: FormData) =>
    request(path, { method: "PUT", body }),
  del: (path: string) => request(path, { method: "DELETE" }),
};

export default api;
