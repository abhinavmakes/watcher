import asyncio
import logging

from worker.pipeline import run_pipeline

logger = logging.getLogger(__name__)


async def _run_once() -> None:
    summary = await run_pipeline()
    logger.info("pipeline_completed", extra=summary.model_dump(mode="json"))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_once())


if __name__ == "__main__":
    main()
