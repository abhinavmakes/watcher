from collections.abc import Sequence

from app.core.supabase import SupabaseGateway
from app.models.article import ArticleInput
from app.models.classification import ClassificationOutput


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
