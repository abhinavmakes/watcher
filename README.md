# Watcher

**Real-time AI/tech intelligence — it reads the firehose so you see ~8 clusters, not 100 articles.**

Watcher ingests AI/engineering news from many sources, then runs each article through a typed agent pipeline — **classify → embed → entity-anchored event clustering → synthesize → momentum rank** — and serves the result as a live dashboard of "what matters today," grouped by story rather than by feed.

> **Status (Jun 2026):** ingestion + classification + embeddings + clustering are **built and validated on live data**; synthesis, momentum, the API, and the dashboard are in active development; deploying end of June. Auth + RAG chat are planned post-MVP. See [Status](#status).
>
> _Live demo: coming at deploy._

---

## The problem

Staying current in AI means scanning newsletters (a day late, can't query), Twitter/X (real-time but pure noise), and Hacker News (great but single-source). The same story breaks across a dozen outlets and you read it five times. Watcher's opinion: you don't need 100 articles, you need the **8 stories that moved today** and which 2 you should care about.

## How it works

| Stage | What it does | Status |
|---|---|---|
| **Ingest** | Google News topic feeds + The Verge AI + The Decoder + Hacker News, normalized to one schema; dedup by canonical URL | ✅ |
| **Classify** | Claude Haiku 4.5 assigns domains, a relevance score, a noise flag, and **key entities** — in one structured-output call | ✅ |
| **Embed** | OpenAI `text-embedding-3-small` (768-dim) over a cleaned title+content representation, stored in pgvector | ✅ |
| **Cluster** | Online single-pass event clustering with a **two-tier, entity-anchored** join rule (below) | ✅ |
| **Synthesize** | One gated LLM briefing per cluster — *what happened / what it means* | 🔧 in progress |
| **Momentum** | Recency-weighted growth across sources; stale clusters fade | 🔧 in progress |
| **Serve** | FastAPI → Next.js dashboard (cards, momentum, domain filters) | 🔧 in progress |

## The interesting part: entity-anchored event clustering

Same-event news clustering with a single cosine threshold is brittle — set it high and one story fragments into five cards; set it low and unrelated stories merge into mush. Watcher uses the approach the news-clustering literature converged on ([entity-aware streaming clustering](https://arxiv.org/abs/2101.11059)): **combine the dense embedding signal with a sparse entity signal.**

Two articles join the same cluster when:

```
cosine ≥ high_threshold          (near-duplicate coverage — auto-merge)
   OR
cosine ≥ entity_threshold  AND  they share a key entity   (same-story, different angle)
```

This buys recall on a developing story's many angles *without* lowering the cosine floor for unrelated articles — something a single threshold cannot do. The entities come free from the classifier call already in the pipeline.

**Validated on a live run:** 100 articles → 6 clean same-event clusters, including two 10-outlet "hero story" clusters (a Nvidia bond sale and an Anthropic/White House story), with no observed over-merge. Thresholds are calibrated by a dedicated eval (`scripts/eval_clustering.py`) over hand-labeled pairs, not guessed.

## Architecture

```
 Sources: Google News · The Verge · The Decoder · Hacker News
                         │
        ┌────────────────▼────────────────────────────────┐
        │  Ingestion worker  (Python, scheduled)           │
        │  connectors → classify → embed → cluster →        │
        │               synthesize → momentum               │
        │  typed agents via PydanticAI, structured outputs   │
        └────────────────┬────────────────────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │  Supabase  (Postgres + pgvector) │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │  FastAPI  →  Next.js dashboard   │
        └─────────────────────────────────┘
```

## Tech stack

**Backend:** Python · FastAPI · PydanticAI · uv
**Data:** Supabase (Postgres + pgvector)
**Models:** Claude Haiku 4.5 (classification) · OpenAI `text-embedding-3-small` (embeddings) · Gemini 2.5 Flash (synthesis, planned)
**Frontend:** Next.js (App Router) · Tailwind _(in progress)_
**Hosting:** Railway (worker + API) · Vercel (frontend)

## Engineering decisions worth defending

- **No clustering library.** A greedy single-pass over centroids is a few lines and keeps the decision rule explicit and tunable; `scikit-learn`/`scipy` would impose their own algorithm and hide it.
- **Eval before UI.** Each agent ships with an eval, not just tests — the classifier (precision/recall on a blind-labeled fixture) and clustering (cosine separation on labeled pairs). Tests prove it runs; evals prove it's *correct*.
- **Entities over threshold-tuning.** Rejected whitening / rerankers / LLM-judge clustering as over-engineering for data that already separates cleanly (different-story cosine ≤0.32, same-story ≥0.61); the entity signal was the higher-leverage, simpler fix.
- **PydanticAI, not LangChain.** The pipeline is a linear typed DAG, not a cyclic agent graph — typed inputs/outputs in plain Python beat a graph DSL here.

## Status

| Done | In progress | Planned |
|---|---|---|
| Multi-source ingestion + dedup | Synthesis (gated LLM briefings) | GitHub OAuth |
| Classification (domains, relevance, noise, entities) | Momentum scoring | RAG chat (BYOK) |
| Embeddings + pgvector | FastAPI endpoints | GitHub Trending / Product Hunt sources |
| Entity-anchored event clustering | Next.js dashboard + deploy | Retention/prune job |
| Classifier + clustering evals | | |

## Run locally (backend)

```bash
cd backend
# put Supabase + Claude + OpenAI keys in a .env at the repo root
uv sync
uv run pytest                    # tests
uv run python -m worker.run      # one ingestion pass
uv run python -m scripts.eval_clustering   # clustering threshold eval
```

More detail: [`docs/PRD.md`](docs/PRD.md) (product), [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) (roadmap), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (schema), [`DECISIONS.md`](DECISIONS.md) (design log).
