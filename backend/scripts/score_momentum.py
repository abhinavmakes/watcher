"""Momentum verification pass.

Recomputes ``momentum_score`` + ``status`` for every active cluster against live
Supabase — the same logic ``worker/pipeline._score_momentum`` runs each pipeline pass,
but standalone so you can verify momentum without re-paying the classifier/synthesis LLM
cost. Dry-run by default (prints what it would write); pass ``--write`` to persist.

Run: ``uv run python -m scripts.score_momentum [--write]`` (needs SUPABASE creds).
"""

import argparse
import asyncio
from datetime import UTC, datetime

from app.core.config import settings
from app.core.supabase import create_supabase_gateway
from app.services.cluster_store import fetch_active_cluster_arrivals, update_cluster_momentum
from app.services.momentum import is_stale, score_momentum


async def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute momentum for active clusters.")
    parser.add_argument("--write", action="store_true", help="persist scores (default: dry run)")
    args = parser.parse_args()

    gateway = await create_supabase_gateway(settings)
    now = datetime.now(UTC)
    arrivals_by_cluster = await fetch_active_cluster_arrivals(gateway)

    rows: list[tuple[str, int, float, float, bool]] = []
    for cluster_id, arrivals in arrivals_by_cluster.items():
        score = score_momentum(arrivals, now, settings.momentum_half_life_hours)
        stale = is_stale(arrivals, now, settings.momentum_stale_hours)
        newest_age_h = (
            min((now - a).total_seconds() / 3600 for a in arrivals) if arrivals else float("inf")
        )
        rows.append((cluster_id, len(arrivals), newest_age_h, score, stale))

    rows.sort(key=lambda r: r[3], reverse=True)
    print(f"{'cluster_id':36}  {'n':>3}  {'newest_age_h':>12}  {'score':>7}  status")
    for cluster_id, n, age_h, score, stale in rows:
        status = "stale" if stale else "active"
        print(f"{cluster_id:36}  {n:>3}  {age_h:>12.1f}  {score:>7.3f}  {status}")

    if args.write:
        for cluster_id, _, _, score, stale in rows:
            await update_cluster_momentum(
                gateway, cluster_id, momentum_score=score, status="stale" if stale else "active"
            )
        print(f"\nwrote {len(rows)} clusters")
    else:
        print(f"\ndry run — {len(rows)} clusters scored, nothing written (pass --write to persist)")


if __name__ == "__main__":
    asyncio.run(main())
