from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


class SupabaseConfigError(RuntimeError):
    pass


@lru_cache
def get_supabase_admin() -> Client:
    if settings.supabase_url is None or settings.supabase_service_key is None:
        raise SupabaseConfigError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")

    return create_client(str(settings.supabase_url), settings.supabase_service_key)
