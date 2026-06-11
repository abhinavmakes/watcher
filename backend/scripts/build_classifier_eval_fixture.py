import argparse
import asyncio
import json
import logging
import random
from pathlib import Path
from typing import Any

from app.core.supabase import get_supabase_gateway
from app.models.article import ArticleInput
from app.models.classifier_eval import LabeledArticle

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "classifier_eval.json"
_SELECT_COLUMNS = "source,title,url,canonical_url,content,published_at,source_meta,is_noise"


async def _fetch_rows() -> list[dict[str, Any]]:
    gateway = await get_supabase_gateway()
    result = await gateway.table("articles").select(_SELECT_COLUMNS).execute()
    return list(result.data)


def _to_article(row: dict[str, Any]) -> ArticleInput:
    return ArticleInput(
        source=row["source"],
        title=row["title"],
        url=row["url"],
        canonical_url=row["canonical_url"],
        content=row.get("content"),
        published_at=row.get("published_at"),
        source_metadata=row.get("source_meta") or {},
    )


def _select_balanced(
    rows: list[dict[str, Any]], limit: int, noise_frac: float, seed: int
) -> list[dict[str, Any]]:
    """Sample a class-balanced subset.

    The stored ``is_noise`` is the *classifier's* guess. It is used only to balance the
    sample so both classes are well represented — it is never written to the fixture, so
    your labeling stays blind.
    """
    rng = random.Random(seed)
    noise = [row for row in rows if row.get("is_noise") is True]
    signal = [row for row in rows if row.get("is_noise") is False]
    rng.shuffle(noise)
    rng.shuffle(signal)

    n_noise = min(len(noise), round(limit * noise_frac))
    n_signal = min(len(signal), limit - n_noise)
    picked = noise[:n_noise] + signal[:n_signal]
    rng.shuffle(picked)  # shuffle so row position can't leak the suspected class
    return picked


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="Build an unlabeled classifier eval fixture.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--noise-frac", type=float, default=0.4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    rows = asyncio.run(_fetch_rows())
    if not rows:
        raise RuntimeError("No articles in Supabase; run the pipeline first")

    picked = _select_balanced(rows, args.limit, args.noise_frac, args.seed)
    labeled = [LabeledArticle(article=_to_article(row)) for row in picked]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps([item.model_dump(mode="json") for item in labeled], indent=2) + "\n",
        encoding="utf-8",
    )

    suspected_noise = sum(1 for row in picked if row.get("is_noise") is True)
    logger.info(
        "classifier_eval_fixture_built",
        extra={
            "available": len(rows),
            "written": len(labeled),
            "suspected_noise": suspected_noise,
            "output_path": str(args.output),
        },
    )


if __name__ == "__main__":
    main()
