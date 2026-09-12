import asyncio
import logging

import httpx

from app.connectors.hackernews import HackerNewsConnector
from app.connectors.rss import RssConnector
from app.core.config import settings
from app.core.supabase import get_supabase_gateway
from worker.pipeline import ConnectorSpec, run_pipeline

logger = logging.getLogger(__name__)

# Attributes on every LogRecord; anything else on a record came from a logger `extra=`.
_RESERVED_LOG_ATTRS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class _ExtraFormatter(logging.Formatter):
    """Append the `extra=` payload the default formatter silently drops, so each pipeline
    stage's counts land in the logs — the difference between a demo-legible run and a wall
    of bare event names."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_LOG_ATTRS and not key.startswith("_")
        }
        if not extras:
            return base
        rendered = " ".join(f"{key}={value}" for key, value in extras.items())
        return f"{base}  {rendered}"


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_ExtraFormatter("%(levelname)-5s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


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
        max_redirects=5,
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
    _configure_logging()
    asyncio.run(_run_once())


if __name__ == "__main__":
    main()
