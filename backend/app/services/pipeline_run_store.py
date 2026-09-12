from typing import Any, cast

from app.core.supabase import SupabaseGateway
from app.models.pipeline_run import PipelineRunSummary

_RUN_SUMMARY_COLUMNS = (
    "id, started_at, completed_at, status, articles_fetched, articles_classified, "
    "clusters_created, clusters_updated, cost_usd, tokens_in, tokens_out, "
    "stage_timings, error_message"
)


async def fetch_recent_runs(gateway: SupabaseGateway, limit: int) -> list[dict[str, Any]]:
    result = await (
        gateway.table("pipeline_runs")
        .select(_RUN_SUMMARY_COLUMNS)
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return cast(list[dict[str, Any]], result.data)


async def insert_pipeline_run(
    gateway: SupabaseGateway,
    summary: PipelineRunSummary,
) -> None:
    summary_json: dict[str, Any] = summary.model_dump(mode="json")
    row = {
        "started_at": summary_json["started_at"],
        "completed_at": summary_json["completed_at"],
        "status": summary_json["status"],
        "articles_fetched": summary_json["articles_fetched"],
        "articles_classified": summary_json["articles_classified"],
        "articles_skipped_known": summary_json["articles_skipped_known"],
        "articles_skipped_old": summary_json["articles_skipped_old"],
        "clusters_updated": summary_json["clusters_updated"],
        "clusters_created": summary_json["clusters_created"],
        "clusters_scored": summary_json["clusters_scored"],
        "clusters_stale": summary_json["clusters_stale"],
        "source_stats": summary_json["source_stats"],
        "error_message": summary_json["error_message"],
        "cost_usd": summary_json["cost_usd"],
        "tokens_in": summary_json["tokens_in"],
        "tokens_out": summary_json["tokens_out"],
        "stage_timings": summary_json["stage_timings"],
    }

    await gateway.table("pipeline_runs").insert(row).execute()
