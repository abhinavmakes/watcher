function normalizeBase(raw: string | undefined): string {
  const fallback = "http://localhost:8000";
  const value = raw && raw.trim() ? raw.trim() : fallback;
  return value.replace(/\/+$/, "");
}

export const API_BASE_URL = normalizeBase(process.env.NEXT_PUBLIC_API_BASE_URL);

// Fixtures are the default so the UI is developable before a live worker run.
// Flip to the live API with NEXT_PUBLIC_USE_MOCKS=false.
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

// Dev-only preview hook: with mocks on, make the feed throw a simulated 429 so the
// rate-limit toast is viewable without a live API. Leave unset in normal use.
export const SIMULATE_429 = process.env.NEXT_PUBLIC_SIMULATE_429 === "true";
