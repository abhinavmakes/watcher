from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.supabase import SupabaseGateway, get_supabase_gateway
from app.models.run_api import RunPage, RunSummaryCard
from app.services.pipeline_run_store import fetch_recent_runs

router = APIRouter()


@router.get("/runs")
async def get_runs(
    gateway: Annotated[SupabaseGateway, Depends(get_supabase_gateway)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> RunPage:
    rows = await fetch_recent_runs(gateway, limit)
    return RunPage(runs=[RunSummaryCard(**row) for row in rows])
