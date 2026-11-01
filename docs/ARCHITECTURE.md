# Architecture

How Watcher is built today. Design rationale and the alternatives I rejected are in
[`DECISIONS.md`](../DECISIONS.md).

## System

Three processes that never call each other. The worker writes, the API reads, and the browser
only ever talks to the API.

```
 Hacker News + RSS feeds
          │
 ┌────────▼─────────────────────────────────────────────┐
 │ Ingestion worker (Python, GitHub Actions, one-shot)   │
 │ fetch → dedup → classify → embed → cluster →          │
 │ synthesize → momentum                                 │
 └────────┬─────────────────────────────────────────────┘
          │ service-role key (server side only)
 ┌────────▼───────────────────┐
 │ Supabase                   │
 │ Postgres + pgvector, RLS   │
 └────────┬───────────────────┘
          │ same key, read only
 ┌────────▼───────────────────┐        ┌────────────────────────┐
 │ FastAPI read API (Vercel)  │◄───────│ Next.js site (Vercel)  │
 │ GET only, rate limited     │ /api/* │ server + client fetch  │
 └────────────────────────────┘        └────────────────────────┘
```

Vercel serves both the site and the API from one domain: `vercel.json` routes `/api/*` to the
FastAPI service and everything else to Next.js, so the browser makes same-origin requests.

## Pipeline

`backend/worker/pipeline.py` runs the stages in order. Each stage records its wall time, and
every run writes one `pipeline_runs` row (counts, tokens, cost, per-stage timings), including
failed runs.

| Stage | What happens |
|---|---|
| Fetch | Hacker News and the RSS feeds in `RSS_FEED_URLS` are fetched concurrently into one `ArticleInput` shape. A connector that fails is recorded in `source_stats` and does not stop the run. |
| Dedup | By canonical URL (`url_normalizer.py`), within the run and against the database. |
| Age filter | Articles published more than `MAX_ARTICLE_AGE_DAYS` (14) ago are dropped, so a feed's archive does not rank as breaking news. |
| Skip known | URLs already stored never reach the LLM. This is the largest recurring cost saving. |
| Classify | One structured-output call per new article: up to three domains (14 allowed), a 0-1 relevance score, a noise flag and up to eight key entities. Noise stops here. |
| Embed | `text-embedding-3-small`, truncated to 768 dimensions, over the title, the first 8,000 characters of the body and the feed tags. Stored in pgvector. |
| Cluster | Online single-pass clustering against open stories (below). Singletons are not persisted as stories. |
| Synthesize | One call per new story, and per existing story that gained articles (its eight newest are sent), producing a headline, a summary and a one-line "so what". |
| Momentum | Recompute every active story's score and mark stale ones. |

Agents are [PydanticAI](https://ai.pydantic.dev/) agents with typed outputs. `build_model()` in
`app/agents/llm.py` maps a `provider:model` setting (for example `openai:gpt-6-luna`) to a
model, so changing provider is an environment change.

### Clustering rule

An article joins its closest story when either holds:

- cosine similarity ≥ 0.78 (existing story) or 0.75 (a story forming in the same run), or
- cosine similarity ≥ 0.65 **and** the article shares a key entity with the story.

The entity tier recovers same-story coverage that sits below the cosine floor without lowering
that floor for unrelated articles. A story stops accepting articles 168 hours after its
*earliest* member, so a popular story cannot extend its own window by attracting more articles.
Centroids are running means. The cosine and the rule are hand-written in
`app/services/clustering.py`.

### Momentum

A story's raw score is the sum of `0.5 ^ (age / half_life)` over its members, with a 72-hour
half-life. A member's age is measured from the earlier of its publication time and the time it
was added. A story with no member newer than 168 hours is marked `stale`. The API maps the raw
score to 0-100 with `100 · raw / (raw + 5)`, so the scale stays bounded and `k` can be tuned
without a backfill.

## Data model

Migrations are in `supabase/migrations/`.

| Table | Holds |
|---|---|
| `articles` | One row per article: `canonical_url` (unique), content, publication time, domains, relevance, noise flag, `embedding vector(768)` |
| `clusters` | One row per story: headline, summary, so-what, momentum, status (`active`/`stale`), entities, domains, `centroid vector(768)` |
| `cluster_articles` | Story membership, with the time each article was added |
| `pipeline_runs` | Audit trail per run: fetched, skipped (known / old), classified, clusters created and updated, tokens, cost, stage timings, error |

## API

All routes are under `/api` and read only.

| Route | Returns |
|---|---|
| `GET /api/health` | Liveness and version |
| `GET /api/clusters?limit&offset&domain` | Active stories by momentum, as cards |
| `GET /api/clusters/{id}` | One story and its source articles. Stale stories still resolve, so shared links do not break. |
| `GET /api/runs?limit` | Recent pipeline runs: counts, cost and timings |

Cards expose the 0-100 momentum, not the raw score, and never the centroid. No request path
calls an LLM, so public traffic cannot spend model credits.

## Security

The surface is small on purpose: a public, no-auth, read-only site.

- **No browser-side secrets.** The frontend has no Supabase client. The service-role key lives in
  the worker's and API's server environment only.
- **Row-level security** is enabled on every table with no policies, so the publishable key
  reads nothing. Only the service role, which bypasses RLS, can.
- **Rate limiting** per client IP (default 60 per minute) with `slowapi`. `X-Forwarded-For` is
  ignored unless `TRUSTED_PROXY_HOPS` says how many proxies are in front, because the header is
  client-supplied. The 429 carries `Retry-After` and CORS headers so the site can show a toast.
- **CORS** allows `GET` only, with no credentials. OpenAPI docs are disabled in production.
- **Untrusted text.** LLM output and feed titles are rendered as text, never as HTML, and
  article URLs are checked for an `http(s)` scheme before they become links.
- **Headers.** The site sets a CSP scoped to its own origin, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, a strict referrer policy and a locked-down permissions
  policy.
- **Secrets in CI.** Provider and database keys are GitHub Actions secrets used only by the
  manual ingest workflow, which runs with read-only repository permissions.

## Quality checks

Tests prove the code runs; evals check that it is right.

- `uv run pytest`: unit and API tests with external services mocked.
- `scripts/eval_classifier.py`: 50 hand-labelled articles with thresholds on noise precision
  (≥ 0.90) and recall (≥ 0.75). Labels are written by hand because the model under test is an
  LLM.
- `scripts/eval_clustering.py`: labelled same-story and different-story pairs, used to check
  that similarity separates at the configured thresholds.
- CI runs ruff, `ruff format --check`, mypy (strict), pytest, ESLint, `tsc` and a production
  build on every push and pull request.

## Cost

Model cost is recorded per run. The run on 2026-11-01 classified 357 new articles and cost about
$0.08 on `gpt-6-luna`. The pipeline is cheap because of two gates: known articles never reach the
classifier, and noise never reaches the embedder.
