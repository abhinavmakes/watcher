# Watcher

Real-time tech intelligence that shows you what's gaining momentum before it hits your newsletter.

Watcher ingests from Hacker News and curated RSS feeds every 30 minutes. HN and RSS are the core MVP sources; GitHub Trending and Product Hunt are best-effort secondary connectors added only after the core clustering path works. Watcher clusters related articles using AI agents, scores momentum, and surfaces what matters — not as a firehose, but as a curated intelligence briefing you can explore and query.

## Why this exists

Newsletters are someone else's curation delivered 24 hours late. Twitter is real-time but pure noise. Watcher is the middle ground that doesn't exist: real-time signal, curated by AI agents, personalized to your interests, and visual.

The product's opinion: you don't need to read 50 articles. You need to see 8 clusters and know which 2 matter to you.

## How it works

**Ingestion** — A background worker runs every 30 minutes, pulling first from HN API and curated RSS feeds, then from best-effort GitHub Trending and Product Hunt connectors if they clear the quality bar. Each article is normalized, classified by domain, and embedded into a vector store.

**Clustering** — Articles that talk about the same topic across different sources land in the same cluster via semantic similarity over embeddings. "PydanticAI v2.3 breaking changes" from HN, a GitHub release note, and a blog post all group together automatically.

**Synthesis** — Clusters with 2+ articles, or one article from a high-signal source, get an AI-generated briefing: what happened, what it means, and whether you should care. One-article items are labeled as single-source signals so the product does not fabricate momentum.

**Momentum** — Every cluster has a momentum score tracking how fast it's growing across sources over time. Topics that are accelerating surface to the top. Topics that peaked yesterday fade down. The dashboard feels alive because the data is alive.

**RAG Chat** — Click into any cluster and ask follow-up questions grounded in the actual ingested articles. "What specifically changed in PydanticAI?" pulls from the real GitHub release notes and HN discussion, not from the LLM's training data. Powered by your own API key (BYOK).

## Architecture overview

```
┌─────────────────────────────────────────────────────┐
│  Data Sources (all free)                            │
│  HN API · curated RSS · GitHub Trending · PH       │
└─────────────┬───────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────┐
│  Ingestion Worker (Railway, cron)                   │
│                                                     │
│  Connectors → Classify Agent → Embed → Cluster      │
│  Agent → Synthesis Agent → Momentum Scorer          │
│                                                     │
│  All agents built with PydanticAI                   │
│  Structured outputs at every stage                  │
└─────────────┬───────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────┐
│  Supabase (unified data layer)                      │
│  Postgres · pgvector · Auth · RLS                   │
└─────────────┬───────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────┐
│  API Service (FastAPI, Railway)                     │
│  REST · SSE streaming · RAG + BYOK chat proxy       │
└─────────────┬───────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────┐
│  Dashboard (Next.js, Vercel)                        │
│  Cluster cards · Momentum sparklines · Chat panel   │
└─────────────────────────────────────────────────────┘
```

## Tech stack

**Backend:** Python, FastAPI, PydanticAI, LiteLLM
**Frontend:** Next.js (App Router), Tailwind CSS, Framer Motion
**Database:** Supabase (Postgres + pgvector + Auth)
**LLMs:** Gemini 2.5 Flash-Lite (classification, free tier), Gemini 2.5 Flash (synthesis)
**Embeddings:** Google text-embedding-005
**Hosting:** Railway (API + worker), Vercel (frontend)
**Cost:** ~$5/month on Google free tier

## Key design decisions

**PydanticAI over LangGraph** — The agent pipeline is a linear DAG (classify → embed → cluster → synthesize), not a cyclic state machine. PydanticAI gives typed inputs/outputs with regular Python composition. LangGraph would add graph DSL overhead for a problem that doesn't need it.

**Supabase as unified data layer** — pgvector for semantic search, Postgres for metadata, Auth for OAuth, Row-Level Security for multi-tenant BYOK key storage. One service instead of three (ChromaDB + separate DB + Clerk).

**SSE over WebSocket** — Dashboard updates and chat streaming are both server-to-client patterns. SSE runs over plain HTTP with built-in browser reconnection. WebSocket's bidirectional capability would be unused overhead.

**Model splitting by task** — Classification uses the cheapest model (Flash-Lite, free tier). Synthesis uses a better model (Flash) because it's the product's voice. Standard production pattern that optimizes cost without sacrificing output quality where it matters.

**BYOK with direct provider keys** — Users bring their own OpenAI, Anthropic, or Google API key for the chat feature. No middleman (OpenRouter) forced on users who already pay for a provider. LiteLLM normalizes the provider differences on the backend.

**Risk-first build order** — The first milestone uses only HN and curated RSS because they have the best signal-to-noise for embeddings, clustering, and RAG. Lower-quality firehose sources such as Dev.to are intentionally excluded from the MVP; GitHub Trending and Product Hunt are added only after clustering has been evaluated on real article pairs.

**Hosted Supabase from day 1** — The project is built against the real managed Supabase surface early so Auth, RLS, pgvector, and migrations are exercised before deployment week. Tests isolate database access where possible.

**Seed data for demo readiness** — A small committed fixture set from HN and curated RSS keeps local demos from opening empty while live connector output is sparse.

## Running locally

```bash
# Clone
git clone https://github.com/abhinavmakes/watcher.git
cd watcher

# Backend
cd backend
cp .env.example .env  # Add your Supabase + Gemini keys
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Worker (separate terminal)
python -m worker.run

# Frontend
cd frontend
cp .env.example .env.local  # Add your Supabase + API URLs
npm install
npm run dev
```

## Project structure

```
watcher/
├── backend/
│   ├── app/
│   │   ├── agents/           # PydanticAI agent definitions
│   │   │   ├── classifier.py
│   │   │   ├── clusterer.py
│   │   │   └── synthesizer.py
│   │   ├── connectors/       # Source-specific fetchers
│   │   │   ├── hackernews.py
│   │   │   ├── rss.py
│   │   │   ├── github_trending.py
│   │   │   └── producthunt.py
│   │   ├── api/              # FastAPI routes
│   │   │   ├── clusters.py
│   │   │   ├── chat.py
│   │   │   ├── stream.py
│   │   │   └── preferences.py
│   │   ├── services/         # Business logic
│   │   │   ├── embedding.py
│   │   │   ├── momentum.py
│   │   │   └── retrieval.py
│   │   ├── models/           # Pydantic schemas + DB models
│   │   └── main.py
│   ├── worker/
│   │   ├── pipeline.py       # Orchestrates full ingestion run
│   │   └── run.py            # Cron entry point
│   ├── fixtures/
│   │   └── seed_articles.json
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── Dockerfile.worker
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx          # Dashboard
│   │   ├── cluster/[id]/
│   │   │   └── page.tsx      # Cluster detail + chat
│   │   └── settings/
│   │       └── page.tsx
│   ├── components/
│   │   ├── ClusterCard.tsx
│   │   ├── Sparkline.tsx
│   │   ├── MomentumBadge.tsx
│   │   ├── ChatPanel.tsx
│   │   └── ...
│   ├── hooks/
│   │   ├── useClusters.ts
│   │   ├── useChat.ts
│   │   └── useSSE.ts
│   └── lib/
│       ├── supabase.ts
│       └── types.ts
├── supabase/
│   └── migrations/           # SQL migration files
└── README.md
```

## License

MIT
