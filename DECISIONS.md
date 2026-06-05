# DECISIONS

Architectural decisions and their interview-defense angle. Newest first.

> Drafted by Claude at the developer's request — review and rewrite in your own
> voice; this is the interview-defense muscle.

---

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
