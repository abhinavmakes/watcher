from typing import Any

from app.core.supabase import SupabaseGateway
from app.models.pipeline_run import PipelineRunSummary


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
        "clusters_updated": summary_json["clusters_updated"],
        "clusters_created": summary_json["clusters_created"],
        "clusters_scored": summary_json["clusters_scored"],
        "clusters_stale": summary_json["clusters_stale"],
        "source_stats": summary_json["source_stats"],
        "error_message": summary_json["error_message"],
    }

    await gateway.table("pipeline_runs").insert(row).execute()
