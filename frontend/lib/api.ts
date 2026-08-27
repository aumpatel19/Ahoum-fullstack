"use client";

import axios, {
  AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";

import type { ApiError } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

const ACCESS_KEY = "ahoum.access";
const REFRESH_KEY = "ahoum.refresh";

/**
 * Tokens live in localStorage.
 *
 * The honest trade-off (DECISIONS.md D2): this is readable by any script that
 * manages to run on the page, whereas httpOnly cookies are not. Cookies would
 * have meant CSRF protection on every mutation. For a 24-hour build behind a
 * single origin, the simpler thing that is easy to reason about won.
 */
export const tokenStore = {
  get access(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  get refresh(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    window.localStorage.setItem(ACCESS_KEY, access);
    if (refresh) window.localStorage.setItem(REFRESH_KEY, refresh);
    window.dispatchEvent(new Event("ahoum:auth"));
  },
  clear() {
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
    window.dispatchEvent(new Event("ahoum:auth"));
  },
  get isAuthenticated(): boolean {
    return Boolean(this.access);
  },
};

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStore.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/**
 * A single in-flight refresh, shared by every request that gets a 401 at the
 * same time. Without this, a page that fires four queries on mount would send
 * four refresh requests and three of them would race.
 */
let refreshInFlight: Promise<string> | null = null;

function refreshAccessToken(): Promise<string> {
  if (!refreshInFlight) {
    const refresh = tokenStore.refresh;
    if (!refresh) return Promise.reject(new Error("no refresh token"));

    // A bare axios call: using `api` here would re-enter this interceptor.
    refreshInFlight = axios
      .post<{ access: string }>(`${API_BASE}/auth/refresh/`, { refresh })
      .then((response) => {
        tokenStore.set(response.data.access);
        return response.data.access;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

type RetriableRequest = InternalAxiosRequestConfig & { _retried?: boolean };

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const original = error.config as RetriableRequest | undefined;
    const isAuthCall = original?.url?.includes("/auth/");

    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      try {
        const access = await refreshAccessToken();
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      } catch {
        // The refresh token is gone or expired too: this session is over.
        tokenStore.clear();
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = "/login?error=session_expired";
        }
      }
    }
    return Promise.reject(error);
  },
);

/** Narrow an unknown thrown value to the API's error envelope. */
export function asApiError(error: unknown): ApiError | null {
  if (axios.isAxiosError(error)) {
    const data = (error as AxiosError<ApiError>).response?.data;
    if (data && typeof data.detail === "string") return data;
  }
  return null;
}
