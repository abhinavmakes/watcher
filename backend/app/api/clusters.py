from fastapi import APIRouter, Depends

from app.core.supabase import get_supabase_gateway
from app.models.cluster_api import ClusterCard, ClusterPage

router = APIRouter()


@router.get("/clusters")
async def get_clusters(gateway=Depends(get_supabase_gateway)) -> ClusterPage: ...
