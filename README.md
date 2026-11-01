# Watcher

[![CI](https://github.com/abhinavmakes/watcher/actions/workflows/ci.yml/badge.svg)](https://github.com/abhinavmakes/watcher/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**An AI news feed that does the reading for you.** Watcher pulls in AI and software-engineering
articles, drops the noise, groups coverage of the same event into one story, and writes a short
briefing for each, so you read one card instead of the same launch five times.

**Live: [watcher-news.vercel.app](https://watcher-news.vercel.app)** ·
[How it works](https://watcher-news.vercel.app/how-it-works)

## How it works

```
Hacker News + RSS → dedup → classify → embed → cluster → synthesize → momentum → API → site
```

| Stage | What it does |
|---|---|
| **Ingest** | Hacker News and a configurable list of RSS feeds (engineering blogs and AI news) are fetched concurrently into one schema and deduplicated by canonical URL. Old articles are dropped. |
| **Classify** | One structured-output call per new article returns domains, a 0-1 relevance score, a noise flag and key entities. Articles already stored never reach the model. |
| **Embed** | `text-embedding-3-small` truncated to 768 dimensions, stored in Postgres with pgvector. |
| **Cluster** | Online single-pass event clustering with a two-tier, entity-anchored join rule (below). A story stops accepting articles a week after its first one. |
| **Synthesize** | One briefing per story: a headline, what happened, and why it matters. Rewritten when the story grows. |
| **Momentum** | A recency-weighted decay sum over member publication times. Stale stories fade out of the feed. |
| **Serve** | A read-only FastAPI service and a Next.js site, both on Vercel. |

The ingestion job runs weekly (currently I trigger it manually, as and when I need it, to save
costs). Each run records its token use, cost and per-stage timings; the site shows the latest.

## The interesting part: entity-anchored clustering

A single cosine threshold for "same story" is brittle. Set it high and one event fragments into
five cards; set it low and unrelated stories merge. Watcher combines the dense embedding signal
with a sparse entity signal ([entity-aware streaming clustering](https://arxiv.org/abs/2101.11059)).
Two articles join the same story when:

```
cosine ≥ 0.78                                   near-duplicate coverage
   OR
cosine ≥ 0.65  AND  they share a key entity     same event, different angle
```

That buys recall on a developing story's many angles without lowering the floor for unrelated
articles, which a single threshold cannot do. The entities come free from the classifier call
already in the pipeline. The cosine and the rule are hand-written
([`clustering.py`](backend/app/services/clustering.py)); no clustering library.

**Where it falls short.** The rule was tuned on news-heavy data, where a shared entity meant the
same event. On single-publisher engineering blogs a shared entity can just mean the same
publisher, and `aws` or `google research` then act as cluster magnets that produce publisher
digests instead of events. The feed list now mixes both kinds. In a snapshot of the live feed
(2026-11-01), 13 of 20 stories link to at least two distinct hosts, the largest being 13 articles
from 5 hosts, and the other 7 sit inside a single host. The clustering eval is a small set of
hand-labelled pairs (13), so treat the thresholds as tuned, not proven. Re-running the eval on
the current feed mix is the next piece of work. The trade-off is recorded in
[`DECISIONS.md`](DECISIONS.md).

## Architecture

```
 Hacker News + RSS feeds
          │
 ┌────────▼────────────────────────────┐
 │ Ingestion worker (Python, one-shot,  │
 │ GitHub Actions)                      │
 └────────┬────────────────────────────┘
          │
 ┌────────▼───────────────────┐
 │ Supabase                   │
 │ Postgres + pgvector, RLS   │
 └────────┬───────────────────┘
          │
 ┌────────▼───────────────────┐        ┌────────────────────────┐
 │ FastAPI read API (Vercel)  │◄───────│ Next.js site (Vercel)  │
 └────────────────────────────┘        └────────────────────────┘
```

Three processes that never call each other: the worker writes, the API reads, the browser only
talks to the API. Details, schema and the security model are in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

**Stack:** Python 3.12 · FastAPI · PydanticAI · uv · Supabase (Postgres + pgvector) · OpenAI
(`gpt-6-luna` for classification and synthesis, `text-embedding-3-small` for embeddings;
`build_model()` also routes `anthropic:` models) · Next.js 16 · React 19 · Tailwind 4 · Vercel ·
GitHub Actions

## Engineering decisions

The full log, with the alternatives I rejected, is in [`DECISIONS.md`](DECISIONS.md). A few:

- **Evals, not just tests.** The classifier is scored against 50 hand-labelled articles with
  asymmetric targets (noise precision ≥ 0.90, recall ≥ 0.75), because dropping a good article is
  the failure the product can't afford. Labels are human, since grading an LLM with an LLM
  measures agreement, not correctness.
- **Cost control per stage.** Known articles never reach the LLM, noise never reaches the
  embedder, and every run records its cost. A full run on `gpt-6-luna` costs about $0.08.
- **PydanticAI, not LangChain.** The pipeline is a linear typed DAG, not a cyclic agent graph.
- **A public API with no auth, by design.** Read-only, per-IP rate limiting that ignores spoofable
  headers, GET-only CORS, no LLM call on any request path, and row-level security on every table.
- **Provider is configuration.** `build_model()` routes a `provider:model` setting, so moving
  from Claude to OpenAI was re-checked against the eval and cut cost about 18x.

## Roadmap

Not built yet:

- Chunk-level retrieval with hybrid search (Postgres full-text + vector), measured by recall@k on
  a hand-labelled set.
- A grounding check, so each claim in a briefing cites the source text it came from and numbers
  and dates are verified against it.
- A scheduled run, which is one uncommented line in
  [`ingest.yml`](.github/workflows/ingest.yml).

Out of scope on purpose: auth, multi-user, personalization, a source-management UI, real-time
streaming.

## Run it locally

You need [uv](https://docs.astral.sh/uv/), Node 20+, a Supabase project, and an OpenAI API key.

```bash
# 1. Database: run supabase/migrations/*.sql in filename order (SQL editor or Supabase CLI)

# 2. Backend
cp .env.example .env             # fill in SUPABASE_URL, SUPABASE_SECRET_KEY, OPENAI_API_KEY
cd backend
uv sync
uv run pytest                    # 133 tests, no network or keys needed
uv run python -m worker.run      # one ingestion pass (calls the LLM, costs a few cents)
uv run uvicorn app.main:app --reload    # API on :8000, docs at /docs in development

# 3. Frontend
cd ../frontend
cp .env.example .env.local
npm ci
npm run dev                      # http://localhost:3000
```

Evals (these call the model APIs): `uv run python -m scripts.eval_classifier` and
`uv run python -m scripts.eval_clustering`. With no backend, set `NEXT_PUBLIC_USE_MOCKS=true` in
`frontend/.env.local` to render the typed fixtures.

CI runs ruff, mypy (strict), pytest, ESLint, `tsc` and a production build on every push.

## License

[MIT](LICENSE)
