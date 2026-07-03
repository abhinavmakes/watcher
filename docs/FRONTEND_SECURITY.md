# Frontend Security — POC delta

Extends the **Frontend Checklist** in `AGENTS.md`. That checklist is generic (it assumes
auth / BYOK / a Supabase client). This file is the **POC-specific delta**: it sharpens the
few items that actually apply and marks the rest N/A, based on the shipped backend.

## Threat surface (why it's small)

The POC frontend is a **public, no-auth, read-only cards page**. It talks to **one thing:
the public FastAPI read API** (`GET /clusters`, `GET /clusters/{id}`). Consequences:

- **No secrets on the client.** No auth tokens, no BYOK keys, no Supabase service key.
- **The frontend never talks to Supabase directly.** All data flows through the API, so the
  service key + RLS stay a backend concern. Do **not** add `@supabase/supabase-js` to the
  frontend for the POC — it would reopen a key-exposure surface the API decision closed.
- **No user-generated content is written.** It's read-only; there's no form posting to a DB.

So the real surface reduces to two things: **rendering untrusted text safely**, and
**following untrusted links safely**. Note the **Home/About page copy is first-party and
trusted** — the untrusted-render risk lives only on the feed and detail pages (LLM + feed
content); the Home page's only external touch is its outbound links (e.g. GitHub), which
follow the same link-safety rule below.

## What actually applies (verify these)

- [ ] **XSS via rendered content — the #1 risk.** `title`, `summary`, `so_what` are
  **LLM-generated**; article `title`/`url` come from **external feeds (HN/RSS)**. All
  untrusted. Render them as **text only** — React auto-escapes, so this is safe by default.
  **Never `dangerouslySetInnerHTML`** on these fields. Synthesis output is plain strings
  (`SynthesisOutput` has no markdown), so **do not add a markdown renderer** — if one is
  ever wanted, sanitize with DOMPurify first. Not adding one is the safer default.
- [ ] **External link safety.** `article.url` is attacker-influenceable (it comes from a
  feed). Before rendering as an `href`, **validate the scheme is `http(s)`** (block
  `javascript:` / `data:`). All external links: `target="_blank" rel="noopener noreferrer"`.
- [ ] **Env hygiene.** Only `NEXT_PUBLIC_API_BASE_URL` (the public API origin) is exposed to
  the browser. Nothing else gets `NEXT_PUBLIC_`. No secret is even *available* to leak.
- [ ] **Security headers (defense in depth).** Set a Content-Security-Policy plus
  `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and frame-ancestors in
  `next.config` headers. A public page benefits and it's ~free.
- [ ] **Graceful, non-leaky states.** Handle **loading / error / empty** everywhere. Two
  concrete cases from this backend: (a) the feed is **empty** whenever clusters are stale
  (hide-stale) — show an empty state, not a spinner forever; (b) a **429** must surface a
  "slow down" toast (read the `Retry-After` header the API sends). Never render raw error
  objects/stack traces.
- [ ] **Dependency hygiene.** Prefer **shadcn/ui** (copy-paste components you own → smaller
  supply-chain surface than an installed component lib). Pin versions; run `npm audit`.
- [ ] **Only render the card contract.** The API already withholds raw `momentum_score`,
  the centroid, and `signal_type`. Don't reintroduce a path (e.g. a direct Supabase query)
  that would expose more than the `ClusterCard`/`ClusterDetail` contract.

## N/A for the POC (revisit in v2)

These `AGENTS.md` security items don't apply yet because their features are v2:

- Supabase anon-key handling / auth tokens in the client (no auth).
- BYOK key encryption / never-send-to-frontend (no BYOK).
- `localStorage` token management, auth-gated UI (no auth).

Keep them in mind so the v2 additions don't bolt auth on unsafely — but they're not live risks now.

## Interview angle

"How did you secure the frontend?" — by scoping security to the **actual** surface. A
public, no-auth, read-only page has no tokens or secrets to leak, so the generic auth/BYOK
checklist is mostly N/A. The real risks are **XSS from synthesized/external text** (handled
by rendering as text, never `dangerouslySetInnerHTML`) and **unsafe external links**
(scheme-validated, `rel="noopener noreferrer"`). Keeping the frontend talking only to the
public API — never Supabase directly — keeps the trust boundary and the service key on the
backend.
