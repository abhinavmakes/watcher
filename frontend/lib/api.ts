import { API_BASE_URL } from "@/lib/env";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class RateLimitError extends ApiError {
  readonly retryAfterSeconds: number;

  constructor(retryAfterSeconds: number) {
    super(429, "Rate limited");
    this.name = "RateLimitError";
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

const DEFAULT_TIMEOUT_MS = 10_000;
const FALLBACK_RETRY_AFTER = 60;

function parseRetryAfter(header: string | null): number {
  const seconds = Number(header);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : FALLBACK_RETRY_AFTER;
}

export async function fetchJson<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  // API_BASE_URL is relative ("/api") in production, where the frontend and API share a
  // domain, and absolute in local dev. In the browser, resolve against the page origin. On
  // the server there is no page origin, so use the incoming request's Host header — the
  // same domain whose rewrite serves /api — rather than guessing a Vercel deployment URL.
  let origin: string;
  if (typeof window !== "undefined") {
    origin = window.location.origin;
  } else {
    // Dynamic import: this module is also pulled into client bundles (e.g. the cluster
    // detail view), and next/headers cannot appear in a static import there.
    const { headers } = await import("next/headers");
    const requestHeaders = await headers();
    const host = requestHeaders.get("host");
    if (host) {
      const isLocal = host.startsWith("localhost") || host.startsWith("127.0.0.1");
      const proto = requestHeaders.get("x-forwarded-proto") ?? (isLocal ? "http" : "https");
      origin = `${proto}://${host}`;
    } else {
      origin = "http://localhost";
    }
  }
  const url = new URL(`${API_BASE_URL}${path}`, origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { accept: "application/json" },
    });

    if (res.status === 429) {
      throw new RateLimitError(parseRetryAfter(res.headers.get("retry-after")));
    }
    if (!res.ok) {
      throw new ApiError(res.status, `Request failed (${res.status})`);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(408, "Request timed out");
    }
    throw new ApiError(0, "Network error");
  } finally {
    clearTimeout(timeout);
  }
}
