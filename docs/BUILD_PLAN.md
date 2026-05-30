# Watcher — Build Plan

Three-week build. ~40 hours total. Each week has a clear deliverable that works standalone, so if life interrupts, you still have something shippable.

Build order is risk-first: pipeline with HN + curated RSS → clustering eval → synthesis with gating → API endpoints → frontend → add GitHub/Product Hunt if they clear the quality bar → polish. This front-loads data quality before UI work.

## Current checkpoint

The backend has the first ingestion slice in place:
- HN and RSS connectors normalize into `ArticleInput`
- the worker fetch stage runs connector specs concurrently and records per-source stats
- current-run duplicate articles are removed by `canonical_url`
- `app/services/article_store.py` maps articles into Supabase `articles` rows
- article persistence uses upsert on `canonical_url` so repeated ingestion runs are idempotent
- focused tests cover connector failures, deduplication, empty connector lists, and article-store mapping
- the live Supabase smoke test has passed: running the worker inserts HN
  articles into the hosted `articles` table, stores `source_meta` as JSONB, and
  repeated runs do not create duplicate `canonical_url` rows

The next slice is not clustering yet. First persist each worker execution into
`pipeline_runs` so the backend has an audit trail and the future SSE endpoint
has a table to poll for completed runs. Only after article persistence and run
tracking are stable should embedding/classification work start.

## Week 1: Data pipeline + backend core

**Goal:** By end of week 1, the ingestion pipeline runs end to end with HN + curated RSS, articles are classified and embedded, clustering has been manually evaluated, synthesis is gated, and a FastAPI endpoint returns real cluster data.

### Day 1-2: Foundation (8h)

**Repo setup**
- Create monorepo: `watcher/backend/` and `watcher/frontend/`
- Python project with `pyproject.toml`
- FastAPI app skeleton with health endpoint
- Hosted Supabase project from day 1: create tables, enable pgvector extension, configure Auth
- Run all SQL migrations from ARCHITECTURE.md
- Environment variables in .env, .env.example committed
- Backend deployment files: `backend/Dockerfile` for the API service and `backend/Dockerfile.worker` for the ingestion worker
- Shared `normalize_url()` utility for canonical deduplication from day 1
- Store both `url` and `canonical_url`: original URL for display/clickthrough, canonical URL for deduplication

**First connector: Hacker News**
- Implement HN connector (Firebase API: /v2/topstories, /v2/item)
- Fetch top 30 stories, normalize to ArticleInput schema
- Test: run connector, print normalized articles

**Classification agent**
- Implement classifier with PydanticAI
- Input: ArticleInput → Output: ClassificationOutput (domains, relevance, is_noise)
- Keep classifier module small: prompt, prompt formatter, agent instance, and wrapper function
- Use typed schema and prompt rules as initial guardrails; defer custom guardrail framework until real eval failures justify it
- Test: classify 10 HN articles, verify domain assignments make sense

**Classifier eval set**
- Build a labeled fixture at `backend/fixtures/classifier_eval.json` with 50-100 real HN/RSS articles hand-labeled with expected `is_noise`, primary domain, and a relevance band (low/mid/high)
- Add `scripts/eval_classifier.py` (or `tests/test_classifier_eval.py`) that runs the production classifier over the fixture and prints precision/recall on `is_noise`, per-domain accuracy, and a confusion matrix
- Plain pytest + a JSON fixture; no eval framework needed for this stage
- Target: noise precision ≥ 0.9, noise recall ≥ 0.75. Iterate on prompt until both are met
- Re-run after any prompt change. This is the canonical "how do you know it works" answer for the classifier.

### Day 3-4: Embedding + more connectors (8h)

**Embedding pipeline**
- Google text-embedding-005 integration
- Embed title + content (truncated to 512 tokens)
- Store embedding in pgvector column on articles table
- Test: embed 10 articles, verify vectors stored correctly

**RSS connector**
- Implement RSS connector with feedparser
- Start with 5 feeds (Pragmatic Engineer, Simon Willison, OpenAI blog, Anthropic blog, LangChain blog)
- Normalize to ArticleInput schema
- Canonical URL-based deduplication against existing articles

**Fetch-stage pipeline orchestration**
- Add worker-level connector registration with `ConnectorSpec`
- Run HN and RSS connector fetches concurrently with `asyncio.gather`
- Convert connector failures into per-source `source_stats` instead of failing the whole run
- Keep RSS feed URLs in configuration (`RSS_FEED_URLS`), not hardcoded Python
- Test: both sources succeed, one source fails, no sources registered

**Seed data**
- Add a small seed-data path using real normalized articles from HN + curated RSS
- Commit small real-data fixtures for demo readiness, e.g. `backend/fixtures/seed_articles.json`
- Regenerate fixtures with `python -m scripts.generate_seed_articles` from `backend/`
- Use it only to keep the dashboard/API demoable while live connector output is sparse or flaky
- Do not confuse seed fixture generation with database seeding: the current seed script writes JSON only. Supabase should be tested by running the real worker path against the hosted database.

**Supabase persistence smoke test**
- Ensure migrations from `supabase/migrations/` have been applied to the hosted Supabase project
- Configure `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in the local `.env`
- Wire the worker entrypoint to create a `SupabaseGateway` and pass it into `run_pipeline`
- Run one pipeline pass with a small HN limit and optional RSS feeds
- Verify the `articles` table contains normalized rows with `source`, `url`, `canonical_url`, `published_at`, and `source_meta`
- Re-run the worker once and verify duplicate canonical URLs do not create duplicate article rows

### Day 5: Clustering eval + synthesis gating + API (8h)

**Manual clustering eval**
- Add `scripts/eval_clustering.py`
- Use the same embedding model and input formatting as production
- Run roughly 50 article pairs through embeddings and print cosine similarity scores
- Manually label at least 10 "should cluster" pairs and 10 "should not cluster" pairs
- Use the results to confirm or adjust `CLUSTER_EXISTING_SIMILARITY_THRESHOLD` and `CLUSTER_NEW_SIMILARITY_THRESHOLD`
- Do not start frontend work until this script shows believable separation on real Watcher data

**Clustering agent**
- Phase 1: cosine similarity between new article embeddings and existing cluster centroids
- Articles above 0.85 threshold join existing clusters
- Remaining articles: agglomerative clustering (scipy.cluster.hierarchy) with 0.83 threshold
- Phase 2: LLM call to name new clusters
- Update cluster centroids (running average of member embeddings)
- Update cluster domains as the union of member article domains

**Synthesis agent**
- Implement synthesizer with PydanticAI (Gemini 2.5 Flash)
- Runs only on clusters that changed this pipeline run and pass the synthesis gate
- Synthesis gate: cluster has 2+ articles, or one article from a high-signal source such as a curated RSS feed, official release blog, or research blog
- One-article items are labeled with `signal_type="single_source"`; low-signal solo items must not use language implying broad momentum
- Output: title, summary, so_what, key_entities

**Synthesis eval (LLM-as-judge)**
- Hand-pick 10-15 real clusters and run the synthesizer over them
- Add `scripts/eval_synthesis.py`: passes each (cluster, synthesis) pair to a judge model (Gemini 2.5 Flash with a fixed rubric) scoring factuality (claims grounded in source articles), no-hedging, and "so what" specificity on a 1-5 scale
- Store rubric, judge prompt, and per-cluster scores in the script output so results are reproducible
- Target: mean factuality ≥ 4, no item with factuality < 3. Iterate on the synthesizer prompt or gating rules if the bar is missed.

**Momentum scoring**
- Count articles per cluster in time buckets (6h, 24h, 48h)
- Weighted formula, normalize to 0-100
- Mark stale clusters (no new articles in 48h)
- Do not delete old articles during ingestion; freshness state and retention cleanup are separate concerns

**Pipeline orchestration**
- worker/pipeline.py: orchestrate full flow
  fetch → dedup → classify → embed → cluster → synthesize → score
- Week 1 pipeline uses HN + curated RSS only
- Insert pipeline_runs record
- Include per-connector source_stats (returned, duplicates, classified, noise, errors)
- Handle individual connector failures gracefully (log and continue)

**API endpoints**
- GET /clusters (paginated, sorted by momentum, domain filter)
- GET /clusters/:id (detail with articles)
- GET /health
- Test: run pipeline once, hit API, verify real data returns

**End of week 1 checkpoint:** The pipeline ingests from HN + curated RSS, classifies, embeds, clusters, passes a manual clustering eval, applies synthesis gating, and scores momentum. The API returns real cluster data. You can curl the endpoint and see actual intelligence briefings or single-source signals.

---

## Week 2: Auth + BYOK chat + live updates

**Goal:** By end of week 2, users can sign in, set preferences, store API keys, ask RAG-powered questions, see live updates via SSE, and optionally benefit from GitHub/Product Hunt connectors after the core pipeline already works.

### Day 6-7: Auth + preferences + BYOK (8h)

**Supabase Auth integration**
- Enable GitHub OAuth in Supabase dashboard
- API middleware: validate Supabase JWT on protected endpoints
- Test: sign in flow works, JWT validates correctly

**Preferences endpoints**
- GET /preferences, PUT /preferences
- RLS policies active on user_preferences table
- Test: set interests, verify they persist

**BYOK key management**
- POST /keys: encrypt API key with AES-256-GCM, store in user_keys
- GET /keys: return provider + model + key_hash (never the key itself)
- DELETE /keys/:provider
- Encryption key from environment variable
- Keep BYOK provider/model catalog separate from pipeline model settings; backend catalog should drive both frontend dropdowns and backend validation
- Test: store a key, verify it's encrypted in DB, verify decrypt works

### Day 8-9: RAG chat (8h)

**Retrieval service**
- Embed user question using Google embedding API
- pgvector similarity search: top 5 whole articles within the specified cluster
- Format retrieved articles with source attribution
- No `article_chunks` table for MVP; whole-article retrieval is intentional

**Chat endpoint**
- POST /chat: accepts message + cluster_id
- Retrieves user's encrypted key, decrypts
- Uses a tool-capable chat agent for open-ended cluster questions; ingestion remains a deterministic DAG
- Initial tools: get cluster metadata, retrieve relevant cluster articles, fetch citation metadata
- Builds prompt/tool context from retrieved source articles + user question
- Calls LiteLLM with user's provider/model/key
- Streams response back via SSE (StreamingResponse)
- Test: ask a question about a real cluster, verify answer cites sources

**Retrieval eval with Ragas**
- Add `scripts/eval_retrieval.py` using Ragas (`pip install ragas`)
- Build 20 hand-crafted question/expected-context pairs across 5-8 real clusters in `backend/fixtures/retrieval_eval.json`
- Run Ragas metrics: `context_precision`, `context_recall`, `faithfulness`, `answer_relevancy`
- Ragas is the resume-recognized name for RAG eval; this is the canonical "how do you know retrieval works" answer
- Target: context_precision ≥ 0.8, faithfulness ≥ 0.85. Iterate on top-k, embedding input formatting, or tool selection if missed.

**Relevance scoring**
- When fetching clusters, if user is authenticated:
  - Check user interests against cluster domains
  - Add relevance_match boolean to response
  - Sort: matched clusters weighted higher (momentum * 1.2 if matched)

### Day 10: SSE + bonus connectors (4h)

**SSE endpoint**
- GET /stream/updates
- Polls pipeline_runs every 30 seconds
- When new completed run detected, push refresh event
- Handle client disconnect gracefully

**GitHub trending connector**
- Scrape github.com/trending (no official API)
- Or use an unofficial API wrapper
- Normalize to ArticleInput
- Treat as best-effort; scraper failure must be recorded in `source_stats` and must not fail the pipeline

**Product Hunt connector**
- GraphQL API, today's posts
- Normalize to ArticleInput
- Treat as best-effort; missing token or GraphQL errors must be recorded in `source_stats` and must not fail the pipeline

**End of week 2 checkpoint:** Full backend is functional. Users can sign in, set interests, store BYOK keys, ask RAG questions about clusters with streaming responses, and receive SSE notifications when the pipeline runs. HN + curated RSS are the reliable core sources; GitHub and Product Hunt are connected if they clear the best-effort bar.

---

## Week 3: Frontend + polish + ship

**Goal:** By end of week 3, the full product is deployed and demo-ready with a polished README and optional blog post.

### Day 11-12: Core frontend (8h)

**Dashboard page**
- Next.js App Router setup
- Supabase client SDK integration
- Server component: fetch clusters on initial load
- ClusterCard component: title, synthesis, momentum sparkline, domain tags
- MomentumBadge component with animated sparklines (Framer Motion)
- StatsRow component with count-up animation
- DomainFilters component with animated card filtering
- Time separators between cluster groups
- TopBar with logo, live indicator, sign-in button

**Cluster detail page**
- Dynamic route: /cluster/[id]
- Full synthesis display
- Source articles list
- Back button

### Day 13: Chat + settings + auth UI (6h)

**Chat panel**
- ChatPanel component on cluster detail page
- Streaming response display with token-by-token rendering
- Inline citation tags
- Loading / locked states (no auth, no key)

**Settings page**
- Interest picker (tag-based multi-select)
- BYOK key management table
- Add key form: provider selector → key input → model dropdown
- Delete key functionality

**Auth flow**
- Sign in with GitHub button (Supabase)
- Avatar / initials in top bar when signed in
- Auth-gated UI elements (chat panel, settings)

### Day 14: SSE + interactivity (4h)

**Live updates**
- useSSE hook: subscribe to /stream/updates
- On refresh event: SWR/React Query revalidation
- New cluster entrance animation
- Stats re-count animation
- "Updated X min ago" live timestamp

**Hover interactions**
- Card hover: border shift + lift
- Sparkline redraw on hover
- Domain chip toggle animation

**Search**
- Client-side filter over cluster titles and synthesis text
- Debounced input

### Day 15: Deploy + README + demo (4h)

**Deployment**
- Railway: deploy API service + worker (separate services, same repo)
- Vercel: deploy Next.js frontend
- Connect Supabase to both
- Set all environment variables
- Verify cron schedule works on Railway
- End-to-end test: pipeline runs → data appears on dashboard → chat works

**README polish**
- Screenshots / GIF of the dashboard
- Architecture diagram
- Clear setup instructions
- "Why this exists" and "Key design decisions" sections

**Demo video (optional but recommended)**
- 2-minute screen recording showing:
  - Dashboard with live clusters
  - Clicking into a cluster
  - Asking a RAG question and seeing streamed response
  - Setting interests and seeing relevance badges
- Upload to README or host on YouTube

**End of week 3 checkpoint:** Watcher is live, deployed, and demo-ready. The README tells the story in 30 seconds. The product works end-to-end. You can link it on your resume, share it on Twitter, and walk through the architecture in an interview.

---

## Risk mitigation

**GitHub Trending scraper breaks:** Treat GitHub as a best-effort connector. If scraping becomes brittle, fall back to the GitHub Search API for recently active repositories or launch with HN + curated RSS. Two high-signal source classes are enough for the MVP demo if clustering and synthesis are strong.

**Clustering quality is poor:** Start with 0.85 for existing cluster joins and 0.83 for new orphan clusters, then validate with `scripts/eval_clustering.py` before frontend work. Test roughly 50 article pairs and manually label at least 10 positive and 10 negative examples. If clustering is still bad, raise thresholds and tolerate over-splitting; broad domain-only grouping is only a last-resort demo fallback.

**Synthesis overstates weak signals:** Gate synthesis. Only synthesize clusters with 2+ articles or one article from a high-signal source. Label all one-article cards as "single-source signal" and avoid wording that implies broad community traction.

**Dashboard opens empty:** Keep a seed-data path with real normalized articles from HN + curated RSS. The seed path exists for demo readiness and local development, not as fake production data.

**Google free tier rate limits hit:** 15 RPM is tight if you're processing 500 articles at once. Solution: add a 4-second delay between LLM calls (15 per minute). The pipeline can take 10-15 minutes and that's fine — it runs in the background.

**Supabase pgvector performance:** At 500 articles/day, you'll have ~15K articles after a month. pgvector with IVFFlat index handles this easily. Won't be a problem until 100K+ rows.

**Old data accumulates:** Do not add destructive deletes to the normal ingestion
pipeline. For MVP, hide stale clusters and keep articles for deduplication, RAG,
debugging, and clustering evaluation. Add a separate retention job after core
pipeline quality is proven: delete or archive pipeline runs older than 30 days,
stale clusters older than 30-60 days, and articles only after their cluster
memberships are no longer needed.

**BYOK key security concerns:** Use AES-256-GCM with a server-side key. Never log keys, never return them to the frontend. This is the industry standard pattern (Cursor, TypingMind, LibreChat all do this). Document it clearly in the README.

## Post-launch priorities (week 4+)

1. Email digest: weekly synthesis delivered via Resend
2. Custom RSS feed management: let users add their own feeds
3. Historical momentum charts: sparkline over days, not just hours
4. Retention cleanup job: archive/delete old pipeline runs, stale clusters, and unneeded old articles outside the ingestion path
5. Provider catalog endpoint for BYOK model dropdowns and backend validation
6. Custom classifier guardrails if real eval outputs show repeated schema-valid but behaviorally wrong classifications
7. OpenRouter as additional BYOK provider option
8. Blog post: "How I built a tech intelligence dashboard with PydanticAI" (Blog 3 or 4 in the series)
