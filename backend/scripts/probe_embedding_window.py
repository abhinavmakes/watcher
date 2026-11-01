"""Embedding-window probe (plan-day-deploy-and-measure.md H4-H5).

Tests whether `embedding_max_content_chars=2000` (the pre-fix value) versus `8000`
(current) plausibly drove the publisher-digest clustering regression that `PLAN.md`
attributes solely to the entity-anchored merge rule.

Raw within-publisher cosine is confounded by shared subject matter (AWS posts really
are about similar things), so this measures a difference-in-differences instead, where
topic similarity appears in both arms and largely cancels:

    delta_ij = cos_8000(i, j) - cos_2000(i, j)

Both embeddings go through the production path (`format_embedding_input`), with
`settings.embedding_max_content_chars` monkeypatched between the two windows — the
formatter itself is never reimplemented.

Writes nothing to the database. Reads article content, embeds in memory, prints.
~212 embeddings, ~$0.01.

Run: ``uv run python -m scripts.probe_embedding_window``
"""

import asyncio
import itertools
from collections import defaultdict
from dataclasses import dataclass

from app.core.config import settings
from app.core.supabase import SupabaseGateway, get_supabase_gateway
from app.models.article import ArticleInput
from app.services.clustering import cosine_similarity
from app.services.embeddings import embed_texts, format_embedding_input

_MIN_CONTENT_CHARS = 2500
_MIN_ARTICLES_PER_PUBLISHER = 6
_WINDOW_NARROW = 2000
_WINDOW_WIDE = 8000

# Pre-registered decision rule (see DECISIONS.md, 2026-09-13) — do not adjust
# after seeing the result.
_CONFIRM_BALANCED_WITHIN = -0.03
_CONFIRM_D = -0.02
_CONFIRM_PCT_NEGATIVE = 70.0
_CONFIRM_MIN_DIRECTIONAL_PUBLISHERS = 4
_REFUTE_BALANCED_WITHIN = -0.01


@dataclass(frozen=True)
class _CorpusArticle:
    publisher: str
    content_len: int
    article: ArticleInput


async def _fetch_corpus(gateway: SupabaseGateway) -> list[_CorpusArticle]:
    result = await (
        gateway.table("articles")
        .select("canonical_url,url,title,content,source_meta")
        .eq("source", "rss")
        .eq("is_noise", False)
        .execute()
    )

    candidates: list[_CorpusArticle] = []
    for row in result.data:
        content = row.get("content") or ""
        if len(content) < _MIN_CONTENT_CHARS:
            continue
        source_meta = row.get("source_meta") or {}
        publisher = source_meta.get("feed_title")
        if not publisher:
            continue
        article = ArticleInput.model_validate(
            {
                "source": "rss",
                "title": row["title"],
                "url": row["url"],
                "canonical_url": row["canonical_url"],
                "content": content,
                "source_metadata": source_meta,
            }
        )
        candidates.append(_CorpusArticle(publisher, len(content), article))

    counts: dict[str, int] = defaultdict(int)
    for candidate in candidates:
        counts[candidate.publisher] += 1
    qualifying = {p for p, n in counts.items() if n >= _MIN_ARTICLES_PER_PUBLISHER}
    return [c for c in candidates if c.publisher in qualifying]


async def _embed_at_window(articles: list[ArticleInput], window: int) -> list[list[float]]:
    original = settings.embedding_max_content_chars
    settings.embedding_max_content_chars = window
    try:
        texts = [format_embedding_input(article) for article in articles]
    finally:
        settings.embedding_max_content_chars = original
    return await embed_texts(texts)


async def main() -> None:
    gateway = await get_supabase_gateway()
    corpus = await _fetch_corpus(gateway)
    if not corpus:
        print(
            f"No qualifying articles (need >={_MIN_ARTICLES_PER_PUBLISHER} per publisher, "
            f"content >={_MIN_CONTENT_CHARS} chars)."
        )
        return

    articles = [c.article for c in corpus]
    vectors_narrow = await _embed_at_window(articles, _WINDOW_NARROW)
    vectors_wide = await _embed_at_window(articles, _WINDOW_WIDE)

    within_deltas: dict[str, list[float]] = defaultdict(list)
    across_deltas: list[float] = []
    for i, j in itertools.combinations(range(len(corpus)), 2):
        delta = cosine_similarity(vectors_wide[i], vectors_wide[j]) - cosine_similarity(
            vectors_narrow[i], vectors_narrow[j]
        )
        if corpus[i].publisher == corpus[j].publisher:
            within_deltas[corpus[i].publisher].append(delta)
        else:
            across_deltas.append(delta)

    publisher_article_counts: dict[str, int] = defaultdict(int)
    for c in corpus:
        publisher_article_counts[c.publisher] += 1

    per_publisher_means = {
        publisher: sum(deltas) / len(deltas) for publisher, deltas in within_deltas.items()
    }

    print(f"\n{'publisher':32} {'n_articles':>10} {'n_pairs':>8} {'mean_delta_within':>18}")
    for publisher in sorted(per_publisher_means):
        deltas = within_deltas[publisher]
        print(
            f"{publisher[:32]:32} {publisher_article_counts[publisher]:>10} "
            f"{len(deltas):>8} {per_publisher_means[publisher]:>+18.4f}"
        )

    all_within = [d for deltas in within_deltas.values() for d in deltas]
    balanced_within = sum(per_publisher_means.values()) / len(per_publisher_means)
    pooled_within = sum(all_within) / len(all_within)
    mean_across = sum(across_deltas) / len(across_deltas) if across_deltas else float("nan")
    d_stat = balanced_within - mean_across
    pct_negative = 100 * sum(1 for d in all_within if d < 0) / len(all_within)
    publishers_negative = sum(1 for m in per_publisher_means.values() if m < 0)

    print("\n--- estimators ---")
    print(f"publisher-balanced mean delta_within: {balanced_within:+.4f}")
    print(f"pooled mean delta_within:              {pooled_within:+.4f}")
    print(f"mean delta_across:                     {mean_across:+.4f}")
    print(f"D (balanced_within - across):          {d_stat:+.4f}")
    print(f"% within-pairs with delta < 0:         {pct_negative:.1f}%")
    print(
        f"publishers with mean delta_within < 0: {publishers_negative}/{len(per_publisher_means)}"
    )

    over_wide_cap = sum(1 for c in corpus if c.content_len > _WINDOW_WIDE)
    mid_range = len(corpus) - over_wide_cap
    print("\n--- composition ---")
    print(f"{len(corpus)} qualifying articles across {len(per_publisher_means)} publishers")
    print(f"  >{_WINDOW_WIDE} chars (both arms truncated):                 {over_wide_cap}")
    print(
        f"  {_MIN_CONTENT_CHARS}-{_WINDOW_WIDE} chars (wide arm sees the full document): "
        f"{mid_range}"
    )
    print(
        "\nNote: format_embedding_input prepends the title in both arms, which dampens "
        "delta slightly. That is the production path and is the point."
    )

    print("\n--- pre-registered decision ---")
    if (
        balanced_within <= _CONFIRM_BALANCED_WITHIN
        and d_stat <= _CONFIRM_D
        and pct_negative >= _CONFIRM_PCT_NEGATIVE
        and publishers_negative >= _CONFIRM_MIN_DIRECTIONAL_PUBLISHERS
    ):
        outcome = "CONFIRM"
    elif balanced_within >= _REFUTE_BALANCED_WITHIN:
        outcome = "REFUTE"
    else:
        outcome = "AMBIGUOUS"
    print(f"outcome: {outcome}")
    print("(recorded in DECISIONS.md, 2026-09-13)")


if __name__ == "__main__":
    asyncio.run(main())
