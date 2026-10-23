"""One-off headline rewrite for clusters whose title no longer matches their content.

Dry-run by default (lists active clusters and OPEN/CLOSED under the new 7-day window,
calling no model); pass ``--write`` to actually rewrite. Rewrites *all* active clusters,
not just the open ones: the magnets this fix closes will never gain members again, and
without this pass they would carry wrong headlines until they go stale on their own.

Run: ``uv run python -m scripts.resynthesize_clusters [--write]``
(needs SUPABASE + the synthesis model's API key).
"""

import argparse
import asyncio
from datetime import UTC, datetime

from app.core.config import settings
from app.core.supabase import create_supabase_gateway
from app.models.cluster import ExistingCluster
from app.services.cluster_store import fetch_active_cluster_arrivals
from app.services.clustering import open_clusters
from worker.pipeline import resynthesize_clusters


async def main() -> None:
    parser = argparse.ArgumentParser(description="Rewrite headlines for active clusters.")
    parser.add_argument("--write", action="store_true", help="persist rewrites (default: dry run)")
    args = parser.parse_args()

    gateway = await create_supabase_gateway(settings)
    active = await gateway.table("clusters").select("id, title").eq("status", "active").execute()
    titles = {row["id"]: row["title"] for row in active.data}

    member_times = await fetch_active_cluster_arrivals(gateway)
    placeholders = [ExistingCluster(id=cid, centroid=[], article_count=0) for cid in titles]
    joinable = open_clusters(
        placeholders, member_times, datetime.now(UTC), settings.cluster_window_hours
    )
    open_ids = {c.id for c in joinable}

    for cluster_id, title in titles.items():
        status = "OPEN" if cluster_id in open_ids else "CLOSED"
        print(f"{cluster_id[:8]}  {status:6}  {title}")

    if not args.write:
        print(f"\ndry run — {len(titles)} active clusters, nothing written")
        print("pass --write to persist")
        return

    rewritten = await resynthesize_clusters(gateway, list(titles))
    print(f"\nrewrote {rewritten} of {len(titles)}")

    after = await gateway.table("clusters").select("id, title").eq("status", "active").execute()
    for row in after.data:
        print(f"{row['id'][:8]}  {row['title']}")


if __name__ == "__main__":
    asyncio.run(main())
