# Watcher

**Real-time AI/tech intelligence — it reads the firehose so you see ~8 clusters, not 100 articles.**

Watcher ingests AI/engineering news from many sources, then runs each article through a typed agent pipeline — **classify → embed → entity-anchored event clustering → synthesize → momentum rank** — and serves the result as a live dashboard of "what matters today," grouped by story rather than by feed.

> **Status (Aug 2026):** the full pipeline — ingest → classify → embed → cluster → synthesize → momentum — plus the read API and the dashboard are **built and running on a cron**. Current work is chunk-level retrieval and a grounding check, so that every claim in a briefing cites the source text it came from and every number is verified against it. Plan: [`docs/PLAN.md`](docs/PLAN.md).
>
> _Live demo: coming at deploy._

---

## The problem

Staying current in AI means scanning newsletters (a day late, can't query), Twitter/X (real-time but pure noise), and Hacker News (great but single-source). The same story breaks across a dozen outlets and you read it five times. Watcher's opinion: you don't need 100 articles, you need the **8 stories that moved today** and which 2 you should care about.

## How it works

| Stage | What it does | Status |
|---|---|---|
| **Ingest** | Long-form engineering blogs (AWS ML + Architecture, Meta Engineering, Google Research, BAIR, GitHub, Julia Evans, Simon Willison, Pragmatic Engineer), alongside AI news feeds for multi-outlet coverage, + Hacker News, normalized to one schema; dedup by canonical URL | ✅ |
| **Classify** | Claude Haiku 4.5 assigns domains, a relevance score, a noise flag, and **key entities** — in one structured-output call | ✅ |
| **Embed** | OpenAI `text-embedding-3-small` (768-dim) over a cleaned title+content representation, stored in pgvector | ✅ |
| **Cluster** | Online single-pass event clustering with a **two-tier, entity-anchored** join rule (below); a story stops accepting articles a week after its first one | ✅ |
| **Synthesize** | One LLM briefing per cluster, rewritten when the story gains articles (Claude Sonnet 4.6) — *what happened / what it means* | ✅ |
| **Momentum** | Recency-weighted decay sum over member publication times; stale clusters fade | ✅ |
| **Serve** | FastAPI read API → Next.js dashboard (cards, momentum, domain filters) | ✅ |
| **Retrieve** | Chunk-level retrieval + hybrid search, measured by recall@k on a hand-labeled set | 🔧 in progress |
| **Ground** | Every claim carries chunk IDs; numbers and dates verified against the retrieved text | 🔧 in progress |

## The interesting part: entity-anchored event clustering

Same-event news clustering with a single cosine threshold is brittle — set it high and one story fragments into five cards; set it low and unrelated stories merge into mush. Watcher uses the approach the news-clustering literature converged on ([entity-aware streaming clustering](https://arxiv.org/abs/2101.11059)): **combine the dense embedding signal with a sparse entity signal.**

Two articles join the same cluster when:

```
cosine ≥ high_threshold          (near-duplicate coverage — auto-merge)
   OR
cosine ≥ entity_threshold  AND  they share a key entity   (same-story, different angle)
```

This buys recall on a developing story's many angles *without* lowering the cosine floor for unrelated articles — something a single threshold cannot do. The entities come free from the classifier call already in the pipeline.

Thresholds are calibrated by a dedicated eval (`scripts/eval_clustering.py`) over hand-labeled pairs, not guessed.

**Known limitation, honestly stated.** That rule was tuned on a news-heavy corpus, where a shared entity meant *same event* — ten outlets covering one story. The feed mix has since moved to long-form engineering blogs to provide the body text chunk-level retrieval needs, and on single-publisher blogs a shared entity means *same publisher*: `aws` and `google research` now act as cluster magnets, producing publisher digests ("AWS publishes six production guides") rather than events. Multi-outlet event clustering is **not** currently demonstrable on this corpus. Re-running the clustering eval against the new distribution — and letting it decide the threshold rather than hand-tuning — is the next task in [`docs/PLAN.md`](docs/PLAN.md). The tradeoff is recorded in [`DECISIONS.md`](DECISIONS.md). News feeds were brought back alongside the blogs so multi-outlet grouping has same-event coverage to work on again.

## Architecture

```
 Sources: AWS · Meta Eng · Google Research · BAIR · GitHub · jvns · Simon Willison · HN
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
**Models:** Claude Haiku 4.5 (classification) · OpenAI `text-embedding-3-small` (embeddings) · Claude Sonnet 4.6 (synthesis)
**Frontend:** Next.js (App Router) · Tailwind _(in progress)_
**Hosting:** GitHub Actions cron (ingestion worker) · EC2 (read API) · Vercel (frontend)

## Engineering decisions worth defending

- **No clustering library.** A greedy single-pass over centroids is a few lines and keeps the decision rule explicit and tunable; `scikit-learn`/`scipy` would impose their own algorithm and hide it.
- **Eval before UI.** Each agent ships with an eval, not just tests — the classifier (precision/recall on a blind-labeled fixture) and clustering (cosine separation on labeled pairs). Tests prove it runs; evals prove it's *correct*.
- **Entities over threshold-tuning.** Rejected whitening / rerankers / LLM-judge clustering as over-engineering for data that already separated cleanly *on the news corpus* (different-story cosine ≤0.32, same-story ≥0.61); the entity signal was the higher-leverage, simpler fix. Those numbers are distribution-specific — see the limitation above.
- **PydanticAI, not LangChain.** The pipeline is a linear typed DAG, not a cyclic agent graph — typed inputs/outputs in plain Python beat a graph DSL here.

## Status

| Done | In progress | Planned |
|---|---|---|
| Multi-source ingestion + dedup | Chunk-level retrieval (`article_chunks`, HNSW) | Hybrid search (Postgres FTS + vector, RRF) |
| Classification (domains, relevance, noise, entities) | Labeled retrieval eval (recall@k, MRR) | Grounding check (numbers + dates, no LLM judge) |
| Embeddings + pgvector | `signal_type='single_source'` for long-form singletons | Retrieve → draft → check → retry loop |
| Entity-anchored clustering (see limitation above) | Clustering eval re-run on the new distribution | MCP server exposing the briefing |
| Momentum scoring + staleness | | Retention/prune job |
| Synthesis (gated LLM briefings) | | |
| Read API + Next.js dashboard | | |
| Classifier + clustering evals | | |

Explicitly **not** planned: auth, multi-user, personalization, a source-management UI, real-time
streaming, mobile. Reasons in [`docs/PLAN.md`](docs/PLAN.md#non-goals).

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
