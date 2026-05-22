# Watcher — Architecture

This document describes the technical architecture of Watcher: service boundaries, data flow, agent pipeline, database design, API surface, and key tradeoffs.

## System overview

Watcher is composed of three independently deployable services and one managed data layer.

```
┌──────────────────┐     ┌──────────────────┐
│  Ingestion Worker │     │   API Service     │
│  (Railway, cron)  │     │  (Railway, always) │
│                   │     │                    │
│  Runs every 30min │     │  Serves dashboard  │
│  Fetches sources  │     │  SSE streaming     │
│  Runs agent pipe  │     │  RAG chat proxy    │
│  Writes to DB     │     │  Auth middleware    │
└────────┬──────────┘     └────────┬───────────┘
         │                         │
         │    ┌────────────────┐   │
         └───►│   Supabase     │◄──┘
              │                │
              │  Postgres      │
              │  pgvector      │
              │  Auth (OAuth)  │
              │  RLS policies  │
              └────────────────┘
                       ▲
                       │
              ┌────────┴───────┐
              │   Next.js App  │
              │  (Vercel)      │
              │                │
              │  Dashboard     │
              │  Cluster detail│
              │  Settings      │
              └────────────────┘
```

**Ingestion Worker** — A Python process triggered on a 30-minute cron schedule via Railway. It fetches articles from all data sources, runs the four-stage agent pipeline (classify → embed → cluster → synthesize), computes momentum scores, and writes results to Supabase. It has no HTTP endpoints. It runs, completes, and exits.

**API Service** — A FastAPI application running continuously on Railway. It reads from Supabase and serves the frontend via REST endpoints, SSE streaming for live updates, and a RAG-powered chat endpoint that proxies LLM calls using the user's BYOK API key. Supabase Auth JWTs are validated as middleware.

**Supabase** — The unified data layer. Postgres stores articles, clusters, user preferences, and encrypted BYOK keys. pgvector handles embedding storage and similarity search. Supabase Auth provides GitHub OAuth. Row-Level Security ensures users can only access their own preferences and keys. Watcher uses a hosted Supabase project from day 1; tests should isolate database access behind service boundaries where possible instead of requiring a local Supabase stack.

**Next.js Dashboard** — The frontend deployed on Vercel. Server components fetch initial cluster data. Client-side hooks subscribe to SSE for live updates and handle the chat interaction. Supabase client SDK manages auth state.

## Why these boundaries

The worker and API are separate processes because they have different failure modes and resource profiles. If the ingestion pipeline crashes on a malformed RSS feed or gets stuck on a slow source API, the API continues serving the dashboard uninterrupted. The worker is CPU-intensive during agent execution; the API is I/O-bound serving requests. Separating them means neither starves the other.

Both deploy from the same monorepo on Railway. Railway supports multiple services from a single repo with separate Dockerfiles or entry points.

## Data flow

### Ingestion pipeline (every 30 minutes)

```
1. FETCH
   Connectors pull from each source in parallel (asyncio.gather)
   Core sources for MVP quality:
   ├── HN: /v2/topstories, fetch top 30
   └── RSS: feedparser over 10-15 curated feeds

   Secondary connectors, added after core clustering works:
   ├── GitHub: /trending endpoint (scrape, no official API)
   └── Product Hunt: GraphQL API, today's posts

   Excluded from MVP:
   └── Dev.to: high volume, but weak signal-to-noise for this product's
       intelligence briefings and clustering demo

2. NORMALIZE
   Each connector outputs a unified ArticleInput schema:
   {
     source: "hn" | "rss" | "github" | "producthunt",
     title: str,
     url: str,               # original source URL for display/clickthrough
     canonical_url: str,     # normalized URL used for deduplication
     content: str,           # body text or description
     published_at: datetime,
     source_metadata: dict    # source-specific fields (HN score, GH stars, etc.)
   }

3. DEDUPLICATE
   Canonical URL-based dedup against existing articles in DB.
   URLs are canonicalized before comparison: lowercase host, remove www,
   strip UTM/tracking params, normalize trailing slashes.
   Skip articles already ingested in previous runs.

4. CLASSIFY (PydanticAI agent, Gemini Flash-Lite)
   Input: ArticleInput
   Output: ClassifiedArticle {
     domains: list[str],       # e.g. ["ai_agents", "python", "open_source"]
     relevance_score: float,   # 0.0 - 1.0, how relevant to tech/AI
     is_noise: bool            # true = skip (press releases, spam, off-topic)
   }
   Articles with is_noise=true are stored but excluded from clustering.

5. EMBED (Google text-embedding-005)
   Input: title + whole article content, capped to the configured embedding limit
   Output: vector(768)
   Stored in pgvector column on the articles table.

6. CLUSTER (PydanticAI agent + cosine similarity)
   Two-phase process:
   a) Semantic grouping: compute pairwise cosine similarity between new
     articles and existing cluster centroids. Articles with similarity
      > 0.85 join existing clusters. Remaining articles are grouped among
      themselves using agglomerative clustering (scipy) with a 0.83 similarity
      threshold. Both thresholds are configurable via environment variables.
   b) Cluster naming: for new clusters, an LLM call generates a title
      and validates the grouping makes sense. Uses Flash-Lite.

   Output: ClusterResult {
     updated_clusters: list[ClusterUpdate],
     new_clusters: list[NewCluster],
     orphans: list[ArticleID]   # articles that don't fit anywhere
   }

7. SYNTHESIZE (PydanticAI agent, Gemini 2.5 Flash)
   Runs ONLY on clusters that changed this pipeline run and pass the
   synthesis gate:
   - clusters with 2+ articles
   - or single-article clusters from high-signal sources such as curated
     RSS feeds, official release blogs, or research blogs

   Single low-signal articles are labeled as "single-source signal" and do
   not get language implying broad community momentum.

   Input: cluster title + all article contents in the cluster
   Output: Synthesis {
     title: str,          # may refine the auto-generated title
     summary: str,        # 2-3 sentence factual summary
     so_what: str,        # 1-2 sentence editorial take
     key_entities: list[str]
   }
   This is the product's voice. Uses the better model (Flash, not Lite).

8. SCORE MOMENTUM
   Not an agent. Pure math.
   For each cluster, count articles in time buckets:
   - last 6 hours
   - 6-24 hours ago
   - 24-48 hours ago
   Momentum = weighted_recent / weighted_total
   Weights: [3, 1, 0.5] for [6h, 6-24h, 24-48h]
   Normalized to 0-100 scale.
   Clusters with no new articles in 48h marked as "stale."

9. RECORD PIPELINE RUN
   Insert into pipeline_runs: {started_at, completed_at, status,
   articles_fetched, articles_classified, clusters_updated, clusters_created,
   source_stats}
```

### Clustering threshold calibration

Before frontend work starts, run a manual eval script against real Watcher
articles:

```
scripts/eval_clustering.py
  → embeds article pairs with the same model/input formatting as production
  → prints cosine similarity scores
  → compares at least 10 manually labeled "should cluster" pairs and
    10 "should not cluster" pairs
  → confirms or adjusts the configured 0.85 / 0.83 thresholds
```

This is intentionally a small offline script, not a product feature. It
front-loads the highest demo risk: bad cluster merges.

### Seed data

The repo includes small real-data fixtures from HN and curated RSS for local
development and demo readiness. Seed data must use the same normalized article
schema as live connectors, including `url` and `canonical_url`, so it exercises
the real pipeline path instead of becoming a separate fake-data mode. Regenerate
the fixture from `backend/` with:

```bash
python -m scripts.generate_seed_articles
```

### Dashboard request flow

```
User opens dashboard
  → Next.js server component fetches GET /clusters from API
  → API queries Supabase: clusters + article counts + momentum scores
  → Returns sorted by momentum (descending), with domain filters
  → Page renders with cluster cards

User subscribes to SSE
  → Client opens EventSource to GET /stream/updates
  → API polls pipeline_runs table every 30s
  → When new completed run detected, pushes event: {type: "refresh"}
  → Client refetches cluster data via SWR/React Query revalidation
```

### RAG chat flow

```
User types question in cluster detail chat panel
  → Client sends POST /chat {message, cluster_id, provider, model}
  → API validates Supabase Auth JWT
  → API retrieves user's encrypted API key from user_keys table
  → API decrypts the key

  → RETRIEVAL:
    1. Embed the user's question using server-side Google embedding API
    2. Query pgvector: find top 5 most similar articles
       within the specified cluster (filtered by cluster_id via join)
    3. Format retrieved whole articles as context

  → GENERATION:
    1. Build messages array:
       - System: "Answer based on the provided context. Cite sources."
       - Context: retrieved articles with source attribution
       - User: original question
    2. Call LiteLLM with user's provider/model/key
    3. Stream response back via SSE

User sees streaming response with inline citations
```

MVP retrieval uses one embedding per article and retrieves whole articles as
context. There is intentionally no `article_chunks` table in the initial
schema because the source mix is mostly short-form content. Chunking would
improve precision for long-form posts, but it is deferred until the content
length distribution justifies the extra schema, ingestion, and retrieval
complexity.

## Database schema

### Tables

**articles**
```sql
CREATE TABLE articles (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source        TEXT NOT NULL,          -- 'hn', 'rss', 'github', 'producthunt'
  title         TEXT NOT NULL,
  url           TEXT NOT NULL,          -- original URL for display/clickthrough
  canonical_url TEXT NOT NULL,          -- normalized URL for deduplication
  content       TEXT,
  published_at  TIMESTAMPTZ,
  domains       TEXT[] DEFAULT '{}',    -- set by classification agent
  relevance     FLOAT DEFAULT 0.0,
  is_noise      BOOLEAN DEFAULT false,
  embedding     VECTOR(768),            -- pgvector
  source_meta   JSONB DEFAULT '{}',     -- source-specific metadata
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_articles_embedding ON articles
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_articles_source ON articles (source);
CREATE INDEX idx_articles_created ON articles (created_at DESC);
CREATE UNIQUE INDEX idx_articles_canonical_url ON articles (canonical_url);
```

**clusters**
```sql
CREATE TABLE clusters (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title           TEXT NOT NULL,
  summary         TEXT,                 -- factual summary from synthesis
  so_what         TEXT,                 -- editorial take from synthesis
  momentum_score  FLOAT DEFAULT 0.0,   -- 0-100
  article_count   INT DEFAULT 0,
  status          TEXT DEFAULT 'active', -- 'active', 'stale'
  signal_type     TEXT DEFAULT 'cluster', -- 'cluster', 'single_source'
  key_entities    TEXT[] DEFAULT '{}',
  domains         TEXT[] DEFAULT '{}',  -- union of member article domains
  centroid        VECTOR(768),          -- average embedding of member articles
  first_seen_at   TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_clusters_momentum ON clusters (momentum_score DESC);
CREATE INDEX idx_clusters_status ON clusters (status);
```

**cluster_articles** (join table)
```sql
CREATE TABLE cluster_articles (
  cluster_id  UUID REFERENCES clusters(id) ON DELETE CASCADE,
  article_id  UUID REFERENCES articles(id) ON DELETE CASCADE,
  added_at    TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (cluster_id, article_id)
);
```

**user_preferences**
```sql
CREATE TABLE user_preferences (
  user_id     UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  interests   TEXT[] DEFAULT '{}',     -- e.g. ['ai_agents', 'funding', 'python']
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own prefs" ON user_preferences
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users write own prefs" ON user_preferences
  FOR ALL USING (auth.uid() = user_id);
```

**user_keys** (BYOK API keys, encrypted)
```sql
CREATE TABLE user_keys (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  provider    TEXT NOT NULL,            -- 'openai', 'anthropic', 'google'
  model       TEXT NOT NULL,            -- 'gpt-4.1', 'claude-sonnet-4-6', etc.
  key_hash    TEXT NOT NULL,            -- last 4 chars for display (sk-...xxxx)
  encrypted_key BYTEA NOT NULL,        -- AES-256 encrypted API key
  created_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, provider)
);

ALTER TABLE user_keys ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own keys" ON user_keys
  FOR ALL USING (auth.uid() = user_id);
```

**pipeline_runs**
```sql
CREATE TABLE pipeline_runs (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at          TIMESTAMPTZ NOT NULL,
  completed_at        TIMESTAMPTZ,
  status              TEXT DEFAULT 'running', -- 'running', 'completed', 'failed'
  articles_fetched    INT DEFAULT 0,
  articles_classified INT DEFAULT 0,
  clusters_updated    INT DEFAULT 0,
  clusters_created    INT DEFAULT 0,
  source_stats        JSONB DEFAULT '{}', -- per-connector returned/duplicate/classified/noise/error stats
  error_message       TEXT
);

CREATE INDEX idx_pipeline_runs_status ON pipeline_runs (completed_at DESC);
```

### Key encryption

BYOK API keys are encrypted at rest using AES-256-GCM. The encryption key is stored as an environment variable on Railway, never in the database or code. The flow:

1. User submits API key via POST /keys
2. Backend encrypts with AES-256-GCM using the server-side encryption key
3. Stores encrypted bytes + last 4 chars (for display) in user_keys
4. When needed for a chat request, decrypts in memory, uses, discards
5. Key never logged, never stored in plaintext, never sent back to frontend

## API surface

### Public endpoints (no auth required)

```
GET  /clusters
     Query: ?domain=ai_agents&status=active&limit=20&offset=0
     Returns: paginated list of clusters sorted by momentum
     Response: { clusters: Cluster[], total: int, has_more: bool }

GET  /clusters/:id
     Returns: full cluster detail with synthesis + list of articles
     Response: { cluster: ClusterDetail, articles: Article[] }

GET  /stream/updates
     SSE endpoint. Pushes events when pipeline completes.
     Event: { type: "refresh", pipeline_run_id: str, timestamp: str }

GET  /health
     Response: { status: "ok", last_pipeline_run: str }
```

### Protected endpoints (Supabase Auth JWT required)

```
GET    /preferences
       Returns: { interests: str[] }

PUT    /preferences
       Body: { interests: str[] }
       Returns: { interests: str[] }

POST   /keys
       Body: { provider: str, model: str, api_key: str }
       Returns: { id: str, provider: str, model: str, key_hash: str }

DELETE /keys/:provider
       Returns: { deleted: true }

GET    /keys
       Returns: [{ provider: str, model: str, key_hash: str }]
       Note: never returns the actual API key

POST   /chat
       Body: { message: str, cluster_id: str }
       Returns: SSE stream of chat response tokens
       Uses the user's stored BYOK key for the LLM call
```

## Agent definitions (PydanticAI)

Each agent is a standalone Python module with typed input/output schemas.

### Classification agent

```python
from pydantic import BaseModel
from pydantic_ai import Agent

class ClassificationInput(BaseModel):
    title: str
    content: str
    source: str

class ClassificationOutput(BaseModel):
    domains: list[str]        # constrained to known domain list
    relevance_score: float    # 0.0 - 1.0
    is_noise: bool

classifier = Agent(
    model="google-gla:gemini-2.5-flash-lite",
    result_type=ClassificationOutput,
    system_prompt="""Classify this tech article into domains.
    Available domains: ai_agents, llms, open_source, funding,
    dev_tools, infra, startups, python, research.
    Mark as noise if: press release, job posting, off-topic, spam."""
)
```

### Synthesis agent

```python
class SynthesisInput(BaseModel):
    cluster_title: str
    articles: list[ArticleSummary]

class SynthesisOutput(BaseModel):
    title: str
    summary: str          # 2-3 sentences, factual
    so_what: str          # 1-2 sentences, editorial
    key_entities: list[str]

synthesizer = Agent(
    model="google-gla:gemini-2.5-flash",
    result_type=SynthesisOutput,
    system_prompt="""Generate an intelligence briefing for this cluster.
    Summary: what happened, factually, across all sources.
    So what: why should a tech professional care. Be opinionated.
    Do not hedge. Do not use phrases like 'it remains to be seen.'"""
)
```

## Configuration

All configuration via environment variables. No config files.

```
# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_KEY=         # server-side, full access
SUPABASE_ANON_KEY=            # client-side, RLS enforced

# LLMs (for pipeline, not BYOK)
GOOGLE_API_KEY=               # Gemini Flash-Lite + Flash + embeddings

# Security
ENCRYPTION_KEY=               # AES-256 key for BYOK key encryption

# App
PIPELINE_INTERVAL_MINUTES=30
CLUSTER_EXISTING_SIMILARITY_THRESHOLD=0.85
CLUSTER_NEW_SIMILARITY_THRESHOLD=0.83
MOMENTUM_STALE_HOURS=48
HIGH_SIGNAL_SOURCE_DOMAINS=        # comma-separated domains allowed to get solo synthesis
```

## Deployment

**Railway** hosts two services from the monorepo:
- API service: `backend/Dockerfile`, always-on, port 8000
- Worker: `backend/Dockerfile.worker`, cron trigger every 30 min

The frontend does not need a Dockerfile for MVP because Vercel builds the
Next.js app directly.

**Vercel** hosts the Next.js frontend from `frontend/` directory.

**Supabase** managed instance, free tier (500MB storage, 50K MAU).

Total infrastructure cost: ~$5/month (Railway hobby plan). LLM costs covered by Google AI Studio free tier during development.

## Future considerations (not in MVP)

- Email digest: scheduled synthesis delivery via Resend
- Custom RSS management: let users add their own feeds
- Historical trends: track momentum over weeks, show trajectory charts
- Team views: shared dashboards for companies
- Webhook integrations: push new cluster alerts to Slack/Discord
- OpenRouter as additional BYOK provider option
