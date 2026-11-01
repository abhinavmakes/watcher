function normalizeBase(raw: string | undefined): string {
  const fallback = "http://localhost:8000/api";
  const value = raw && raw.trim() ? raw.trim() : fallback;
  return value.replace(/\/+$/, "");
}

export const API_BASE_URL = normalizeBase(process.env.NEXT_PUBLIC_API_BASE_URL);

// Opt-in: fixtures render only when NEXT_PUBLIC_USE_MOCKS=true. These values are inlined at
// build time, so a deploy that forgets to set one must fail toward the live API, not toward
// a page that looks finished and is entirely fake.
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

// Dev-only preview hook: with mocks on, make the feed throw a simulated 429 so the
// rate-limit toast is viewable without a live API. Leave unset in normal use.
export const SIMULATE_429 = process.env.NEXT_PUBLIC_SIMULATE_429 === "true";
