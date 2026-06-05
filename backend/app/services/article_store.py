from collections.abc import Sequence

from app.core.supabase import SupabaseGateway
from app.models.article import ArticleInput
from app.models.classification import ClassificationOutput


async def fetch_existing_canonical_urls(
    gateway: SupabaseGateway, canonical_urls: Sequence[str]
) -> set[str]:
    """Return which of ``canonical_urls`` are already persisted, so the pipeline can
    classify only unseen articles and avoid re-paying the per-article LLM cost."""
    if not canonical_urls:
        return set()
    result = await (
        gateway.table("articles")
        .select("canonical_url")
        .in_("canonical_url", list(canonical_urls))
        .execute()
    )
    return {row["canonical_url"] for row in result.data}


async def insert_articles(
    gateway: SupabaseGateway, articles: Sequence[tuple[ArticleInput, ClassificationOutput | None]]
) -> int:
    if not articles:
        return 0
    rows = []

    for article, classification in articles:
        article_json = article.model_dump(mode="json")
        row = {
            "source": article_json["source"],
            "title": article_json["title"],
            "url": article_json["url"],
            "canonical_url": article_json["canonical_url"],
            "content": article_json["content"],
            "published_at": article_json["published_at"],
            "source_meta": article_json["source_metadata"],
        }
        if classification is not None:
            classification_json = classification.model_dump(mode="json")
            row["relevance"] = classification_json["relevance_score"]
            row["domains"] = classification_json["domains"]
            row["is_noise"] = classification_json["is_noise"]
        rows.append(row)

    await (
        gateway.table("articles")
        .upsert(rows, on_conflict="canonical_url", ignore_duplicates=True)
        .execute()
    )

    return len(rows)
