from typing import Any

from app.core.config import Settings, settings
from supabase import AsyncClient, create_async_client


class SupabaseConfigError(RuntimeError):
    pass


class SupabaseGateway:
    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    def table(self, table_name: str) -> Any:
        return self._client.table(table_name)

    def rpc(self, function_name: str, params: dict[str, object] | None = None) -> Any:
        return self._client.rpc(function_name, params or {})


_gateway: SupabaseGateway | None = None


async def create_supabase_gateway(app_settings: Settings) -> SupabaseGateway:
    secret_key = app_settings.supabase_secret_value
    if app_settings.supabase_url is None or secret_key is None:
        raise SupabaseConfigError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")

    client = await create_async_client(str(app_settings.supabase_url), secret_key)
    return SupabaseGateway(client)


async def get_supabase_gateway() -> SupabaseGateway:
    global _gateway

    if _gateway is None:
        _gateway = await create_supabase_gateway(settings)

    return _gateway


def clear_supabase_gateway_cache() -> None:
    global _gateway
    _gateway = None
