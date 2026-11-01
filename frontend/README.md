# Watcher — Frontend

Public, read-only UI for the Watcher pipeline. Next.js (App Router), TypeScript (strict),
Tailwind v4, shadcn/ui, Motion, SWR. It talks only to the public read API through
`NEXT_PUBLIC_API_BASE_URL`: no Supabase client, no auth, no secrets in the browser.

## Run

```bash
cp .env.example .env.local
npm ci
npm run dev        # http://localhost:3000
```

Against a live backend, run the API from `backend/` (`uv run uvicorn app.main:app`).
With no backend, set `NEXT_PUBLIC_USE_MOCKS=true` to render the typed fixtures in
`lib/fixtures.ts`.

```bash
npm run lint
npx tsc --noEmit
npm run build
```

## Routes

| Route | What it is |
|---|---|
| `/` | Momentum-ranked story feed with domain filters and the last pipeline run |
| `/cluster/[id]` | One story: the synthesized briefing and its source articles |
| `/how-it-works` | The pipeline, the clustering rule and how quality is measured |

## Notes

- The home page fetches the feed server-side and hands it to SWR as initial data; the
  cluster page fetches on the client with SWR.
- Untrusted text (LLM output, feed titles) is rendered as text only, and article links are
  checked for an `http(s)` scheme before they become an `href`.
- Security headers, including a CSP scoped to the site's own origin, are set in
  `next.config.ts`.
