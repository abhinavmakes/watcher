from collections.abc import Sequence

from app.core.supabase import SupabaseGateway
from app.models.article import ArticleInput
from app.models.classification import ClassificationOutput

# postgREST sends `in.(...)` filters in the request URL; long canonical URLs (e.g. Google
# News redirect links) overflow the gateway's URL-length limit, so query in batches.
_IN_FILTER_BATCH_SIZE = 20


async def fetch_existing_canonical_urls(
    gateway: SupabaseGateway, canonical_urls: Sequence[str]
) -> set[str]:
    """Return which of ``canonical_urls`` are already persisted, so the pipeline can
    classify only unseen articles and avoid re-paying the per-article LLM cost."""
    urls = list(canonical_urls)
    if not urls:
        return set()
    existing: set[str] = set()
    for start in range(0, len(urls), _IN_FILTER_BATCH_SIZE):
        batch = urls[start : start + _IN_FILTER_BATCH_SIZE]
        result = await (
            gateway.table("articles").select("canonical_url").in_("canonical_url", batch).execute()
        )
        existing.update(row["canonical_url"] for row in result.data)
    return existing


async def insert_articles(
    gateway: SupabaseGateway,
    articles: Sequence[tuple[ArticleInput, ClassificationOutput | None]],
    embeddings: dict[str, list[float]] | None = None,
) -> int:
    if not articles:
        return 0
    embeddings = embeddings or {}
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
        embedding = embeddings.get(article.canonical_url)
        if embedding is not None:
            row["embedding"] = embedding
        rows.append(row)

    await (
        gateway.table("articles")
        .upsert(rows, on_conflict="canonical_url", ignore_duplicates=True)
        .execute()
    )

    return len(rows)
