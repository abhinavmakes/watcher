# DECISIONS

Architectural decisions and their interview-defense angle. Newest first.

> Drafted by Claude at the developer's request — review and rewrite in your own
> voice; this is the interview-defense muscle.

---

### 2026-06-21 — Synthesis: purpose-built input model, pure agent, new-clusters-only v1
**What:** Gated LLM briefing (title/summary/so_what) per new cluster via a PydanticAI Anthropic agent (`app/agents/synthesizer.py`). `SynthesisInput`/`SynthesisArticle` are a purpose-built input model that reuses only the vocabulary types (`ArticleSource`, `ArticleDomain`) and carries title/content/source plus the cluster's unioned `key_entities`/`domains` — *not* the `Cluster`/`ArticleInput` objects. `synthesize_cluster` takes a ready `SynthesisInput`; the pipeline assembles it (joins cluster `member_urls` back to the `ArticleInput`s, which still hold the `content` that `EmbeddedArticle` drops). Synthesis runs over `new_clusters` only; results pass to `persist_cluster_result` index-aligned, where the synthesized title overwrites the provisional member-headline and summary/so_what are written in the same insert.
**Why this approach:** The input model is LLM prompt surface — embedding machinery (`centroid`/`vector`/`relevance`) would be noise tokens that degrade output, and embedding `Cluster` would drag clustering internals into the prompt contract. Keeping `synthesize_cluster` as `SynthesisInput → SynthesisOutput` mirrors the classifier (`ArticleInput → ClassificationOutput`) and keeps the agent free of clustering/ingestion coupling; assembly is the pipeline's job. New-clusters-only because they're the only bucket whose member content is in memory this run — `updated` clusters' prior members live only in the DB (a fetch deferred), and singleton `orphans` aren't persisted as clusters. The PRD's "2+ articles" gate arm is already enforced upstream (clustering only emits ≥2-member clusters), so the gate collapsed to "every new cluster." Rejected re-synthesizing `updated` clusters this pass (needs a DB content fetch + prior-summary handling) and resurrecting high-signal orphans as `single_source` clusters (a clustering/persist change) — both flagged as the next slice.
**Interview angle:** "Why a separate input model instead of passing your cluster object to the LLM?" — prompt surface vs internal machinery, decoupling the agent from upstream stages, and how the existing clustering invariant (≥2 members) made half the spec'd gate redundant.

### 2026-06-21 — Synthesis model: Sonnet 4.6 vs Haiku for classification; the env-precedence 404
**What:** Synthesis uses Claude Sonnet 4.6; classification stays on Haiku 4.5. One synthesis call per new cluster, paced by `synthesis_rpm`. Shipping bug: `.env`'s `SYNTHESIS_MODEL` still held the old `google-gla:gemini-2.5-flash`, which overrides the `config.py` default — and since the model-name helper only strips an `anthropic:` prefix, that literal string was sent to the Anthropic API → 404 on every synthesis call while the rest of the pipeline succeeded. Fixed the env value and verified live (15/15 clusters synthesized, 0 failures).
**Why this approach:** Synthesis is the quality-critical surface — the one card the user reads — and runs at low volume (a handful of calls per run), so the marginal cost of the stronger model is small. Classification is high-volume (every fetched article), where Haiku's price dominates, so it stays cheap. Model choice tiers by volume × quality-stakes, not one model everywhere.
**Interview angle:** "How do you pick models across a multi-stage pipeline?" — tier by volume and quality stakes; plus a war story on config precedence (env over code defaults) causing a silent 404 that unit tests missed because they mock the LLM boundary.

### 2026-06-05 — Classifier provider: Gemini Flash-Lite → Claude Haiku 4.5
**What:** Swapped the classification agent to Claude Haiku 4.5 (PydanticAI `AnthropicModel`) and trimmed deps to `pydantic-ai-slim[anthropic]`.
**Why this approach:** Gemini's free tier hit a hard requests-per-day (RPD) wall mid-run; prepaid Claude credits give a controllable hard spend cap, and Haiku is cheap enough (~$0.004/article) for a scheduled pipeline. Rejected padding the prompt past 4,096 tokens to force prompt caching — a hack, and caching silently no-ops below Haiku's cacheable floor.
**Interview angle:** "How did you choose a model and control LLM cost?" — RPM vs RPD limits, prepaid vs metered spend, why caching didn't apply here.

### 2026-06-05 — Dedup before classify (recurring-cost lever)
**What:** The pipeline filters fetched articles against already-persisted `canonical_url`s *before* the classifier runs, and records the skipped count in `pipeline_runs.articles_skipped_known`.
**Why this approach:** Re-classifying the whole pool every run was the dominant recurring cost; dedup-first only classifies the delta (~4–10× cheaper after the cold first run). Rejected cheaper-model / prompt-trimming as smaller levers that also cost quality. Tradeoff: one extra DB read per run (negligible).
**Interview angle:** "Where's the cost in an LLM pipeline and how did you cut it?" — the lever is *what you send*, not *which model*.

### 2026-06-05 — Classifier eval: human-labeled fixture + harness
**What:** A 50-article, class-balanced eval fixture with blind human labels, plus `eval_classifier.py` reporting noise precision/recall, domain overlap, and relevance-band accuracy against fixed targets.
**Why this approach:** Tests prove the code runs; an eval proves the *behavior* is correct. Labeled by hand — not by a model — because the classifier is Claude, so labeling with a Claude model would be circular (shared blind spots). Targets are asymmetric (noise precision ≥0.90 > recall ≥0.75) because a false-positive = dropping a good article, the one failure the product can't afford. Domain uses a deliberately lenient overlap metric (can mask over-tagging) since domain is secondary to the noise gate.
**Interview angle:** "How do you know your classifier is good, and who labeled the ground truth?" — non-circular labeling, metric asymmetry mapped to product cost, and naming the metric's own weakness.

### 2026-06-05 — Taxonomy: removed `culture`; signal = insight, not "technical"
**What:** Dropped the `culture` domain and added a noise rule for nostalgia / retro trivia / standalone quotes, so pure low-substance "interesting" items have no home domain and fall to noise.
**Why this approach:** The eval surfaced that the classifier scored low-substance culture items almost randomly (0.15–0.50). Encoding the editorial stance in the *taxonomy* (no bucket ⇒ noise) is simpler and more consistent than a fuzzy scoring rule. The governing rubric: signal = an actionable insight or fresh perspective, not merely "is it technical" — a business-strategy essay with a real thesis is signal; demoscene nostalgia is not. Rejected a culture-IS-signal rule (an initial misread of the rubric that the eval corrected).
**Interview angle:** "Give an example of your eval changing a design decision." — the eval reversed a taxonomy assumption and tightened the noise definition on real disagreements.
