# Watcher — Frontend

Public, read-only cards UI for the Watcher pipeline. Next.js (App Router) +
TypeScript (strict) + Tailwind v4 + shadcn/ui + Framer Motion + Lucide. Talks only
to the public read API via `NEXT_PUBLIC_API_BASE_URL` — no Supabase client, no
secrets in the browser.

## Dev

```bash
npm run dev
```

Copy `.env.example` to `.env.local`. `NEXT_PUBLIC_USE_MOCKS=true` (default) renders
the UI against typed fixtures so it's developable before a live worker run; set it
to `false` to hit the live API.

## Pages

- `/` — home / about (pitch + how the pipeline works)
- `/feed` — momentum-driven cards grid
- `/cluster/[id]` — cluster detail (synthesis + source articles)

Auth, chat, settings, SSE, and search are v2 and intentionally out of scope.
