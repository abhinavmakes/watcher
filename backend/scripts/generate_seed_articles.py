import asyncio
import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

from app.connectors.hackernews import HackerNewsConnector
from app.connectors.rss import RssConnector
from app.core.config import settings
from app.models.article import ArticleInput
from worker.pipeline import ConnectorSpec, _deduplicate_fetched_articles, _fetch_from_connector

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "seed_articles.json"
SEED_HN_LIMIT = 10
SEED_RSS_LIMIT = 20


def serialize_articles(articles: Sequence[ArticleInput]) -> list[dict[str, Any]]:
    return [article.model_dump(mode="json") for article in articles]


def write_seed_articles(
    articles: Sequence[ArticleInput],
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(serialize_articles(articles), indent=2) + "\n",
        encoding="utf-8",
    )


def _build_seed_connector_specs(client: httpx.AsyncClient) -> list[ConnectorSpec]:
    connector_specs = [
        ConnectorSpec(
            name="hn",
            connector=HackerNewsConnector(client),
            limit=min(settings.hn_fetch_limit, SEED_HN_LIMIT),
        )
    ]

    rss_feed_urls = settings.rss_feed_url_list
    if rss_feed_urls:
        connector_specs.append(
            ConnectorSpec(
                name="rss",
                connector=RssConnector(client, rss_feed_urls),
                limit=min(settings.rss_fetch_limit, SEED_RSS_LIMIT),
            )
        )

    return connector_specs


async def generate_seed_articles(output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        connector_specs = _build_seed_connector_specs(client)
        fetch_results = await asyncio.gather(
            *(_fetch_from_connector(spec) for spec in connector_specs)
        )

    fetched_articles = [article for result in fetch_results for article in result.articles]
    dedup_result = _deduplicate_fetched_articles(fetched_articles)
    if not dedup_result.articles:
        raise RuntimeError("No seed articles fetched; refusing to write an empty fixture")

    write_seed_articles(dedup_result.articles, output_path)

    logger.info(
        "seed_articles_generated",
        extra={
            "fetched": len(fetched_articles),
            "unique": len(dedup_result.articles),
            "duplicates_by_source": dedup_result.duplicates_by_source,
            "source_errors": {
                result.source: result.error for result in fetch_results if result.error is not None
            },
            "output_path": str(output_path),
        },
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(generate_seed_articles())


if __name__ == "__main__":
    main()
