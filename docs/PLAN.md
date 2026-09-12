# PLAN — retrieval + grounding evals in Watcher

Working plan. Read this first. Current state, not narrative.
Background: `docs/worldpulse-scope.md` (scope), `docs/retrieval-idea-audit.md` (audit + measurements).

---

## What's being built

Chunk-level retrieval and a grounding check **inside Watcher**, by replacing the internals of the
existing synthesizer — **not** by adding a second briefing module.

The cluster cards already shipping are ungrounded: `_build_synthesis_input` passes title/content/
source with no article IDs, the output carries no citations, and nothing verifies the model didn't
invent a number. The work makes them grounded: chunk-level retrieval assembles the prompt, every
claim carries chunk IDs, and a checker verifies numbers and dates against the retrieved set.

One product, one arc: *"the cards shipped ungrounded; I made them grounded, here's the before/after."*

---

## Accepted changes (from the audit)

| # | Change | Status |
|---|---|---|
| 1 | Fix `rss.py` to prefer `entry.content[0].value` over `entry.summary`; swap the feed mix toward full-text feeds. **No** `article_fetcher.py`, no trafilatura, no Google News redirect resolution. | Day 1 |
| 2 | No `briefer.py`. Replace the synthesizer's internals; extend `SynthesisOutput` with `chunk_ids`. | Week 1–2 |
| 3 | Implement `signal_type='single_source'` so long-form singletons become 1-member clusters and get briefings. **Gate: `relevance >= 0.8` AND `length(content) >= 1300`** — measured 2026-08-02, that promotes **50** of 275 orphans, giving a 66-card feed rather than a 275-card wall. 0.8 is the floor of the classifier prompt's "useful signal" band, already validated by the classifier eval — reused rather than invented. | Week 1 |
| 4 | Grounding checker: **numbers and dates only**. Report support rate *and* hand-audited checker precision. Entity checking is a normalization swamp — cut. | Week 2 |
| 5 | Chunk-size sweep lives in **Week 2**, not the demo phase. | Week 2 |
| 6 | No novelty claim anywhere. Sell the delta. | Ongoing |

---

## Phases

**Day 1 — data fix. DONE 2026-08-02.** `rss.py` content extraction, feed-mix swap, one pipeline run
(263 fetched / 185 classified / 16 clusters), gate re-measured. Also fixed the un-batched `in_()`
filter in `fetch_existing_canonical_urls`, which crashed the first run attempt at 280 URLs.

**Correction pass — before Week 1. ~half a day.** The feed swap changed the input distribution, and
a heuristic tuned for the old one now misfires. Four items, in order:

1. **Re-run the clustering eval on the new distribution.** `scripts/eval_clustering.py` and its 13
   labelled pairs were built on the old news-heavy corpus. Add ~10 pairs drawn from today's data —
   two unrelated AWS posts, two unrelated Julia Evans posts, labelled `different` — and re-run.
   **Do not touch `cluster_entity_similarity_threshold` until the eval says to.**
   *Why this is the highest-value item in the whole plan:* it converts a regression into
   *"I changed my input distribution and my own eval caught it"* — three evals, one of which earned
   its keep on a real change. Reuses machinery already written. DECISIONS entry: evals are
   distribution-specific.
2. **Fix the README** (see below). Do this before any Week 1 code.
3. Record the `single_source` gate (change #3) as a decision, with the 50-of-275 number.
4. Write the retrieval-corpus definition into the gate section (done, above).

**Week 1 — chunking + pgvector retrieval.** Pure chunker (`app/services/chunking.py`),
`article_chunks` table + HNSW index, chunk persistence wired through the pipeline (needs
`insert_articles` to return the `canonical_url → id` map), `match_chunks()` SQL function,
`app/services/retrieval.py` vector path. Resumable backfill scripts. First real pgvector query in
the repo. Also: `signal_type='single_source'`.

**Week 2 — labeled eval + hybrid + re-measure.** Hand-labeled `question → answer_article_id`
fixture (**hand-written, not LLM-generated** — the classifier eval's non-circularity standard
applies). `eval_retrieval.py` (recall@k, MRR, no LLM calls, query embeddings cached to disk).
Chunk-size sweep. Postgres FTS (`tsvector` + GIN) and RRF fusion (k=60). Grounding checker
(numbers + dates). Re-measure both metrics. **The before/after table is the deliverable.**

**Week 3 — LangGraph retry loop + MCP server.** `retrieve → draft → grounding-check → retry-if-
unsupported`, genuinely cyclic with a conditional edge. Requires updating the `AGENTS.md` LangChain/
LangGraph ban and rewriting the PydanticAI-over-LangChain `DECISIONS.md` entry to say what changed —
an unexplained contradiction is worse than either choice. Then the MCP server.

---

## Blocking gate — CLEARED

**≥50% of the retrieval corpus at ≥1300 chars before any chunker code exists.**

**Retrieval corpus is defined as: RSS articles with non-empty `content`.** HN link posts carry no
body text — they are clustering inputs, not retrieval inputs — and empty rows produce zero chunks.
Neither belongs in a denominator that asks *"will chunking produce anything different from
`articles`?"*

| measurement | value | band |
|---|---:|---|
| 2026-08-02, before Day 1 fix (all non-noise) | 11.1% — 21/190 | RED |
| 2026-08-02, after Day 1 fix (all non-noise) | 42.2% — 152/360 | AMBER |
| 2026-08-02, after Day 1 fix (**retrieval corpus**) | **55.5% — 152/274** | **GREEN** |

**Honesty note:** both denominators were computed after the run, not before. The definition above is
the one that governs, and it is recorded here alongside the alternative so the reframe is visible
rather than quiet. The argument for it is that an empty document is not a short document.

- Bands: ≥50% green · 30–50% fix the feed mix first · <30% stop.
- 1300 chars ≈ 2 chunks at 256 tokens. Use 2500 if chunking at 512.
- Re-measure with the query in `docs/retrieval-idea-audit.md` §6.

Below the gate, the chunk table is a 1:1 copy of `articles` and hybrid-vs-vector measures blurb
retrieval.

Corpus size also cleared: 274 retrieval documents (was 190 total), 152 of them multi-chunk.

---

## Non-goals

Deliberately not built. Each was cut for a reason, not overlooked.

- **Auth and multi-user.** Public corpus, nothing per-user to protect. The `user_preferences` and
  `user_keys` tables are vestigial and should be dropped.
- **Personalization.** Ranking is momentum + retrieval relevance, both measurable against a fixed
  labeled set. Per-user relevance makes every metric here unreproducible.
- **Source management UI.** Feeds are an env var. A CRUD screen for a comma-separated list is a
  CRUD screen.
- **Real-time streaming.** Batch pipeline on a 2-day cron, and the UI says so.
- **Mobile app.** The web UI is responsive.
- **Scheduling beyond a cron line.** The worker is an idempotent one-shot; it needs a trigger, not
  an orchestrator.
- **Summaries of summaries.** Every claim must trace to a source chunk. A summary of a summary has
  no chunk to point at and can't be grounding-checked.

---

## Known state after Day 1 — read before judging the feed

Three things are true of the live feed right now. None is a bug; all three follow from feeding a
news-shaped pipeline a corpus of single-publisher blogs.

- **Clusters are publisher digests, not events.** The merge rule joins two articles when the text is
  similar *and* they share a key entity. On news, a shared entity meant *same story* (ten outlets,
  one Nvidia bond sale). On blogs it means *same publisher* — `aws`, `google research`,
  `julia evans` act as cluster magnets, producing cards like "AWS publishes six production guides"
  and three separate Julia Evans cards. Unresolved on purpose: the correction pass re-runs the
  clustering eval and lets it decide, rather than hand-tuning the threshold now.
- **Momentum currently carries no information.** `raw = Σ 0.5^(age_h/24)`, and every cluster was
  created in the same run, so `raw ≡ member count` exactly: 6 members → 54.5, 3 → 37.5, 2 → 28.6.
  The decay term does nothing until there is age spread across runs. Nothing to fix; just don't
  read the number as "story heat" yet.
- **76% of non-noise articles produce no card** (275 of 360). Singletons are dropped, and
  single-publisher posts are singletons by construction. Change #3 addresses this.

**Decided against: adding news feeds back to restore clustering density.** News articles are short,
produce one chunk each, dilute the retrieval corpus, and cost classifier spend. News serves
clustering; long-form blogs serve retrieval; this project's deliverable is the retrieval delta.
The cost is owned rather than hidden: multi-outlet event clustering is no longer demonstrable on
this corpus, which is why the README has to stop claiming it.

---

## Positioning

**No novelty claim.** Ragas, Phoenix, DeepEval, TruLens all ship retrieval eval and faithfulness
metrics; hybrid RRF on pgvector is a documented Supabase guide. `ARCHITECTURE.md:219` already
specified Ragas. Claiming rarity invites correction from anyone who has used them.

What's being sold is the loop, on a corpus nobody else has measured:

> The metrics are standard and the tools exist. I built a labeled set for my own corpus, measured
> recall@10, changed one thing, and re-measured.

Hand-rolling recall@k (~40 lines) is defended as *"I wanted to own the metric definition and keep
an LLM judge out of the loop"* — not as *"nothing existed."*

**The deliverable is the measured retrieval delta on this corpus.** Everything else is scaffolding.
