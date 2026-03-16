import axios from "axios";
import { API_BASE_URL } from "./config/api";

const ACCESS_TOKEN_KEY = "accessToken";
const REFRESH_TOKEN_KEY = "refreshToken";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

const clearAuthStorage = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  localStorage.removeItem("isLoggedIn");
  localStorage.removeItem("username");
};

let refreshPromise = null;

const refreshAccessToken = async () => {
  if (refreshPromise) {
    return refreshPromise;
  }

  const refresh = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refresh) {
    return null;
  }

  refreshPromise = (async () => {
    try {
      const res = await axios.post(`${API_BASE_URL}/token/refresh/`, { refresh });
      const nextAccess = res?.data?.access || null;
      if (!nextAccess) {
        return null;
      }
      localStorage.setItem(ACCESS_TOKEN_KEY, nextAccess);
      if (res?.data?.refresh) {
        localStorage.setItem(REFRESH_TOKEN_KEY, res.data.refresh);
      }
      return nextAccess;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
};

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY) || localStorage.getItem("token");
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error?.config || {};
    const requestUrl = String(originalRequest?.url || "");
    const isAuthRequest =
      requestUrl.includes("/auth/login/") ||
      requestUrl.includes("/token/refresh/");

    if (error?.response?.status === 401 && !originalRequest._retry && !isAuthRequest) {
      originalRequest._retry = true;
      const nextAccess = await refreshAccessToken();

      if (nextAccess) {
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${nextAccess}`;
        return api(originalRequest);
      }

      clearAuthStorage();
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }

    return Promise.reject(error);
  },
);

export { api };
export default api;
