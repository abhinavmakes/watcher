# Frontend Plan — POC

The build spec for the Watcher POC frontend. Pairs with `docs/FRONTEND_SECURITY.md`
(security delta) and `AGENTS.md` (Frontend Checklist + TypeScript standards + anti-patterns,
applied silently). Agent builds this directly; developer reviews.

## Scope — THREE pages, high polish, nothing else

| Route | Page | Purpose |
|-------|------|---------|
| `/` | **Home / About** | What Watcher is, how the pipeline works, GitHub link, CTA into the feed |
| `/feed` | **Cards grid** | The live cluster cards — the product |
| `/cluster/[id]` | **Cluster detail** | Full synthesis + source articles |

Everything else is **v2** and must NOT be built: auth / sign-in, chat, settings, BYOK, SSE
live updates, search, GitHub/Product Hunt anything. (See the POC-scope note in `BUILD_PLAN.md`.)

## Stack (mandated in AGENTS.md — don't deviate)

Next.js 14+ App Router, **TypeScript strict**, **Tailwind only**, **shadcn/ui**, **Framer
Motion**, **Lucide** icons, **SWR + fetch (no axios)**, ESLint + Prettier. **No three.js /
D3 / chart libraries** — any visualization is custom SVG. **No Supabase client on the
frontend** — it talks only to the public API. Create `frontend/` fresh.

## Data

Client-side fetch (SWR) from the public API via `NEXT_PUBLIC_API_BASE_URL`. Type every response.

- `GET /clusters` → `ClusterPage { cards: ClusterCard[], total, limit, offset }`
- `GET /clusters/{id}` → `ClusterDetail` (all `ClusterCard` fields + `articles: ClusterArticleRef[]`)
- `ClusterCard`: `id, title, summary?, so_what?, momentum (0–100 float), domains[], key_entities[], article_count, status`
- `ClusterArticleRef`: `id, title, url, source, published_at?`

Build against a small **typed mock fixture** matching these shapes so the UI is developable
before a live worker run (the real feed is empty whenever clusters are stale).

**States (all required):** loading, error, and **empty** — the feed is empty whenever
clusters are stale, so show an empty state, not an infinite spinner. On a **429**, show a
"slow down" toast that reads the `Retry-After` header.

## Design direction (opinionated — one hook, not five)

- **Feed = momentum-driven bento grid.** Higher `momentum` → larger / brighter tile. The
  **`so_what` is the hero** (pull-quote treatment) — it's the product's differentiator.
- **Momentum badge = custom SVG** gauge/bar, hot→cool color by value. **NOT a trend line** —
  there is no time-series data (historical momentum is post-launch).
- Domain + key-entity **chips** (Lucide icons); domain-colored accents.
- **Framer Motion**, tasteful: staggered card entrance, `layout` animation on domain filter,
  hover lift. Not gratuitous.
- **Detail page:** full synthesis (`summary` + prominent `so_what`), source-article list
  (source label + safe external link), back button, graceful 404.
- **Domain filter** on the feed (client-side over the loaded cards, or the API `domain`
  param). That's the only interactivity — no search.

## Home / About page content

First-party, trusted copy (no untrusted rendering here). Sections:
- **Hero:** one-line pitch — Watcher turns the AI/tech news firehose into *signal*: it
  clusters coverage of the same story and synthesizes a factual summary + a "so what."
- **How it works:** the pipeline as simple steps — fetch (HN + curated RSS) → classify
  (Haiku) → embed → entity-anchored cluster → synthesize (Sonnet) → momentum score. A small
  step diagram or numbered flow; custom SVG/markup, no chart lib.
- **GitHub link** (external, `rel="noopener noreferrer"`) + a **CTA** into `/feed`.
- Keep it honest about scope: public read-only view; chat/personalization are roadmap.

## Security

Apply `docs/FRONTEND_SECURITY.md` silently. Highlights: render `title`/`summary`/`so_what`/
article-title as **text only** (never `dangerouslySetInnerHTML`, no markdown renderer);
external links (article urls + GitHub) scheme-validated `http(s)` + `rel="noopener
noreferrer"`; only `NEXT_PUBLIC_API_BASE_URL` exposed; CSP + security headers in `next.config`.

## After it renders clean

Draft a `DECISIONS.md` entry (What / Why / Interview angle) for the frontend: client-side
fetch (preserves real IPs + enables the 429 toast), security scoping to the no-auth surface,
and the momentum-viz choice (badge, not a trend line, because there's no time series).
Developer reviews and rewrites in his voice.
