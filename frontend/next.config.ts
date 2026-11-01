import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

// Cross-origin API to allow in connect-src. A relative base ("/api", as in production where
// the API shares the site's domain) is already covered by 'self', so it adds nothing.
function apiOrigin(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (base?.startsWith("/")) return "";
  try {
    return new URL(base ?? "http://localhost:8000").origin;
  } catch {
    return "";
  }
}

// Frontend talks only to the public read API. connect-src is scoped to that origin
// (plus ws: in dev for HMR). Inline script/style allowances are the pragmatic App
// Router default; the surface is a no-auth read-only page with no secrets to protect.
const csp = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "style-src 'self' 'unsafe-inline'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  `connect-src ${["'self'", apiOrigin(), ...(isDev ? ["ws:"] : [])].filter(Boolean).join(" ")}`,
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  // The page lived at /engineering, and links to it may already be shared.
  async redirects() {
    return [{ source: "/engineering", destination: "/how-it-works", permanent: true }];
  },
};

export default nextConfig;
