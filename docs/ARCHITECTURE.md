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

The backend worker and API use the Supabase service role from server-side code
only. Migrations grant the service role table access explicitly; RLS policies
remain the protection boundary for user-owned tables when accessed with user
JWTs. Service-role keys must never be exposed to the frontend.

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

3. DEDUPLICATE + PERSIST
   Canonical URL-based dedup happens in two layers:
   - in-memory dedup within the current fetch batch so downstream stages do
     not process the same canonical URL twice in one run
   - database idempotency through the articles.canonical_url unique index and
     an upsert that ignores already-seen URLs from previous runs

   URLs are canonicalized before comparison: lowercase host, remove www,
   strip UTM/tracking params, normalize trailing slashes.

   The storage boundary lives in `app/services/article_store.py`.
   `insert_articles(gateway, articles)` receives an already-created
   SupabaseGateway, maps `ArticleInput` into the `articles` table shape, uses
   `model_dump(mode="json")` so datetimes and URLs are JSON-safe, and upserts
   rows on `canonical_url`. The worker/service entrypoint owns client creation;
   storage functions only map and execute database operations.

4. CLASSIFY (PydanticAI agent, Claude Haiku 4.5)
   Input: ArticleInput
   Output: ClassificationOutput {
     domains: list[str],       # 0-3 of ArticleDomain, e.g. ["ai_agents", "python"]
     relevance_score: float,   # 0.0 - 1.0, how relevant to tech/AI
     is_noise: bool,           # true = skip (press releases, spam, off-topic)
     reason: str,              # one factual sentence explaining the decision
     key_entities: list[str]   # normalized lowercase named entities, <=8; anchors clustering
   }
   Articles with is_noise=true are stored but excluded from clustering.

5. EMBED (OpenAI text-embedding-3-small, 768-dim)
   Input: title + content (capped to embedding_max_content_chars) + tags
   Output: vector(768)
   Stored in the pgvector `embedding` column on the articles table.
   `format_embedding_input` owns the text shape; `embed_texts` batches calls.

6. CLUSTER (pure-python cosine + entity anchoring — no LLM, no scipy)
   Two passes in `app/services/clustering.py`:
   a) Join existing clusters: for each article, find its best-matching active
      cluster centroid. Two-tier merge rule (`_joins`): cosine >= 0.78 OR
      (cosine >= 0.65 AND shares a key entity).
   b) Form new clusters among the orphans with the same rule at the 0.75 tier.
      A forming group that never gains a 2nd member is a true orphan (dropped).
   Thresholds (config.py): existing 0.78 / new 0.75 / entity 0.65. The entity
   tier (classifier's key_entities) gives recall on same-story coverage without
   lowering the cosine floor for unrelated articles.

   Provisional title = the highest-relevance member's title (set in
   persist_cluster_result); synthesis overwrites it in stage 7.

   Output: ClusterResult {
     new_clusters: list[Cluster],
     updated: dict[cluster_id, list[canonical_url]],  # who joined which existing cluster
     orphans: list[canonical_url]   # singletons that didn't fit anywhere
   }

7. SYNTHESIZE (PydanticAI agent, Anthropic Claude)
   Reuses the already-wired Anthropic stack (same provider as CLASSIFY) rather
   than a second provider — chosen for speed-to-ship. Model in `synthesis_model`.
   Runs ONLY on clusters that changed this pipeline run and pass the
   synthesis gate:
   - clusters with 2+ articles
   - or single-article clusters from high-signal sources such as curated
     RSS feeds, official release blogs, or research blogs

   Single low-signal articles are labeled as "single-source signal" and do
   not get language implying broad community momentum.

   Input: cluster title + all article contents in the cluster
   Output: SynthesisOutput {
     title: str,          # overwrites the provisional title
     summary: str,        # 2-3 sentence factual summary
     so_what: str         # 1-2 sentence editorial take
   }
   This is the product's voice.

8. SCORE MOMENTUM
   Not an agent. Pure math. Runs over ALL active clusters, not just those
   touched this run — a cluster decays / goes stale by elapsed time alone.
   For each cluster, sum a time-decay weight over its members' arrival times
   (cluster_articles.added_at):
     momentum = Σ 0.5 ** (age_hours / MOMENTUM_HALF_LIFE_HOURS)   # half-life 24h
   Sum (not mean) so a cluster that keeps gaining members outranks a stale one.
   Stored raw (≈ effective recent-article count); 0-100 normalization is applied
   at the API/display layer, not here.
   Clusters whose newest member is older than MOMENTUM_STALE_HOURS (48h) → 'stale'.

   Stale does not mean deleted. The ingestion pipeline should mark freshness
   state only; destructive retention cleanup is a separate operational job so
   a partial pipeline failure cannot delete historical data and then fail later
   in classification, embedding, clustering, or synthesis.

9. RECORD PIPELINE RUN
   Insert into pipeline_runs: {started_at, completed_at, status,
   articles_fetched, articles_classified, articles_skipped_known,
   clusters_updated, clusters_created, clusters_scored, clusters_stale,
   source_stats}
```

### Data retention and cleanup

Watcher keeps old articles during the MVP because they are useful for
canonical URL deduplication, clustering evaluation, RAG citations, debugging,
and demo reproducibility. The dashboard should hide or deprioritize stale
clusters, not delete their backing data during ingestion.

Before running Watcher as a long-lived deployment, add a separate retention job:

- delete or archive `pipeline_runs` older than 30 days
- delete or archive stale clusters older than 30-60 days
- delete articles only after their cluster memberships are no longer needed
- never run destructive cleanup inside the normal fetch/classify/embed/cluster
  pipeline

This is deliberately post-MVP scope. At the expected scale of hundreds of
articles per day, retaining several weeks of data is cheap and helps validate
embedding and clustering quality.

### Eval methodology

Every agent in the pipeline has a dedicated eval. Tests prove the code runs;
evals prove the behavior is correct. The two are not the same.

- **Classifier eval** — pytest over a labeled fixture of 50-100 real HN/RSS
  articles. Reports precision/recall on `is_noise`, per-domain accuracy, and a
  confusion matrix. Targets: noise precision ≥ 0.9, recall ≥ 0.75.
- **Clustering eval** — `scripts/eval_clustering.py` (already specified above).
  Calibrates the 0.85/0.83 similarity thresholds against hand-labeled article
  pairs before any frontend work begins.
- **Synthesis eval** — LLM-as-judge with a fixed rubric (factuality, no-hedging,
  "so what" specificity). 10-15 real clusters scored 1-5.
- **Retrieval eval** — Ragas (`context_precision`, `context_recall`,
  `faithfulness`, `answer_relevancy`) over a 20-pair fixture once the RAG chat
  endpoint exists.

Eval fixtures live in `backend/fixtures/` and are committed. Eval scripts are
intentionally small and reproducible — no MLflow, no Weights & Biases, no
custom dashboard for MVP. The bar is: any reviewer can clone the repo, run one
script, and see the numbers.

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

This command writes `fixtures/seed_articles.json`; it does not insert into
Supabase. Once Supabase credentials are configured and migrations are applied,
the next smoke test is to run the worker pipeline with a real gateway and verify
that normalized articles appear in the `articles` table. Seed fixtures remain
the fallback demo data path; the live pipeline remains the source of truth.

### Dashboard request flow

```
User opens dashboard
  → Browser fetches GET /clusters from the API client-side (CORS-allowed origin), NOT via a server component — see note below
  → API queries Supabase: clusters + article counts + momentum scores
  → Returns sorted by momentum (descending), with domain filters
  → Page renders with cluster cards

User subscribes to SSE
  → Client opens EventSource to GET /stream/updates
  → API polls pipeline_runs table every 30s
  → When new completed run detected, pushes event: {type: "refresh"}
  → Client refetches cluster data via SWR/React Query revalidation
```

> **Why client-side fetch, not a Next.js server component (2026-07-01):** the public read API is no-auth, so per-IP rate limiting (slowapi) is the DoS bound — and per-IP only works if the API sees each user's *real* IP. A server-component fetch routes every user through Vercel's egress IP, collapsing per-IP into one shared bucket that would throttle all users together. Client-side fetch also means a `429` reaches the browser, where the frontend can surface a "slow down" toast. (The SSE live-updates path above is **v2** — see the POC-scope note in `BUILD_PLAN.md`.)

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

The chat path is the natural place for a tool-using PydanticAI agent. Unlike
ingestion, user questions are open-ended: the agent may need cluster metadata,
retrieved articles, or a citation lookup before answering. Keep ingestion as a
deterministic Python DAG with narrow structured-output agents; use tools in chat
where the model must choose which retrieval action to take.

Initial chat tools:

- `get_cluster_metadata(cluster_id)` returns title, synthesis, domains,
  momentum, and article count
- `retrieve_cluster_articles(cluster_id, query)` embeds the question and returns
  the most relevant source articles inside that cluster
- `get_article_source(article_id)` returns citation metadata for a cited article

Tool outputs must contain source IDs/URLs so the final answer can cite articles
instead of relying on model memory.

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
  momentum_score  FLOAT DEFAULT 0.0,   -- raw time-decay sum; 0-100 normalized at API
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
  articles_fetched       INT DEFAULT 0,
  articles_classified    INT DEFAULT 0,
  articles_skipped_known INT DEFAULT 0,
  clusters_updated       INT DEFAULT 0,
  clusters_created       INT DEFAULT 0,
  clusters_scored        INT DEFAULT 0,
  clusters_stale         INT DEFAULT 0,
  source_stats           JSONB DEFAULT '{}', -- per-connector returned/duplicate/classified/noise/error stats
  error_message          TEXT
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

### Provider and model catalog

Keep pipeline model configuration separate from the user-facing BYOK provider
catalog.

- Pipeline model names such as `CLASSIFIER_MODEL`, `SYNTHESIS_MODEL`, and
  `EMBEDDING_MODEL` live in backend settings because they are deployment
  configuration.
- BYOK providers and model dropdown options are product metadata. Expose them
  from a backend service such as `app/services/provider_catalog.py` and, when
  needed by the frontend, a read-only API endpoint such as `GET /providers`.
- Do not hardcode BYOK model lists separately in frontend components and backend
  validation. The backend catalog should become the source of truth for both UI
  rendering and key/model validation.
- Do not mix BYOK chat catalog work into pipeline agent slices. Classification,
  synthesis, and embeddings use Watcher's server-side Google configuration; chat
  uses the user's stored provider/model/key through LiteLLM.

## API surface

### Public endpoints (no auth required)

```
GET  /clusters
     Query: ?domain=ai_agents&limit=20&offset=0   (limit max 100; stale hidden server-side — no status param)
     Returns: active clusters sorted by momentum DESC; momentum normalized 0-100 at read time
     Response: ClusterPage { cards: ClusterCard[], total: int, limit: int, offset: int }
     (impl 2026-06-30: store read done; normalization + handler pending)

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

Each agent is a standalone Python module with typed input/output schemas. Keep
agent modules simple until there is real duplication: prompt constants,
formatting helpers, and a `classify_article()`/`synthesize_cluster()` wrapper
are enough. Avoid a shared `agents/base.py` or custom guardrail framework until
two or more agents prove they need the same behavior.

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
    reason: str               # one-sentence local eval/debug reason

classifier = Agent(
    model="anthropic:claude-haiku-4-5-20251001",
    result_type=ClassificationOutput,
    system_prompt="""Classify this tech article into domains.
    Available domains: ai_agents, llms, open_source, funding,
    dev_tools, infra, startups, python, research.
    Mark as noise if: press release, job posting, off-topic, spam."""
)
```

Initial classifier guardrails are schema-level and prompt-level: stable domain
enum values, `relevance_score` bounded to 0.0-1.0, one to three domains for
non-noise articles, and a short reason for local inspection. Add custom
guardrail code only after real classifier outputs show repeated failures such
as empty domains on non-noise articles, high relevance with `is_noise=true`, or
invalid domain values.

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
CLAUDE_API_KEY=               # Claude Haiku 4.5 (classification)
GOOGLE_API_KEY=               # Gemini Flash synthesis + embeddings (planned)

# Security
ENCRYPTION_KEY=               # AES-256 key for BYOK key encryption

# App
PIPELINE_INTERVAL_MINUTES=30
CLUSTER_EXISTING_SIMILARITY_THRESHOLD=0.85
CLUSTER_NEW_SIMILARITY_THRESHOLD=0.83
MOMENTUM_STALE_HOURS=48
MOMENTUM_HALF_LIFE_HOURS=24         # decay half-life (hours) for momentum scoring
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
