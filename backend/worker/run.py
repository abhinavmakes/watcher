import asyncio
import logging

import httpx

from app.connectors.hackernews import HackerNewsConnector
from app.connectors.rss import RssConnector
from app.core.config import settings
from app.core.supabase import get_supabase_gateway
from worker.pipeline import ConnectorSpec, run_pipeline

logger = logging.getLogger(__name__)

# Some feeds (e.g. The Verge) reject requests without a browser-like User-Agent.
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def _run_once() -> None:
    async with httpx.AsyncClient(
        timeout=20.0,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        connector_specs = [
            ConnectorSpec(
                name="hn",
                connector=HackerNewsConnector(client),
                limit=settings.hn_fetch_limit,
            )
        ]

        rss_feed_urls = settings.rss_feed_url_list
        if rss_feed_urls:
            connector_specs.append(
                ConnectorSpec(
                    name="rss",
                    connector=RssConnector(client, rss_feed_urls),
                    limit=settings.rss_fetch_limit,
                )
            )

        gateway = await get_supabase_gateway()
        summary = await run_pipeline(connector_specs, gateway=gateway)

    logger.info("pipeline_completed", extra=summary.model_dump(mode="json"))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_once())


if __name__ == "__main__":
    main()
