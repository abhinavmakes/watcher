from pathlib import Path
from typing import Protocol

import pytest

from app.core.config import Settings
from app.core.supabase import SupabaseConfigError, create_supabase_gateway


class FakeSupabaseFactoryFixture(Protocol):
    calls: dict[str, str]


@pytest.mark.asyncio
async def test_create_supabase_gateway_uses_secret_key(
    fake_supabase_factory: FakeSupabaseFactoryFixture,
) -> None:
    gateway = await create_supabase_gateway(
        Settings.model_validate(
            {
                "supabase_url": "https://watcher.supabase.co",
                "supabase_secret_key": "sb_secret_test",
            }
        )
    )

    assert fake_supabase_factory.calls == {
        "url": "https://watcher.supabase.co/",
        "key": "sb_secret_test",
    }
    assert gateway.table("articles") == "table:articles"
    assert gateway.rpc("match_articles", {"limit": 5}) == ("match_articles", {"limit": 5})


@pytest.mark.asyncio
async def test_create_supabase_gateway_requires_server_credentials() -> None:
    with pytest.raises(SupabaseConfigError, match="SUPABASE_URL and SUPABASE_SECRET_KEY"):
        await create_supabase_gateway(Settings(supabase_url=None, supabase_secret_key=None))


def test_supabase_import_stays_inside_boundary() -> None:
    app_dir = Path(__file__).parents[1] / "app"
    boundary = app_dir / "core" / "supabase.py"
    offenders: list[str] = []

    for path in app_dir.rglob("*.py"):
        if path == boundary:
            continue

        text = path.read_text(encoding="utf-8")
        if "from supabase" in text or "import supabase" in text:
            offenders.append(str(path.relative_to(app_dir)))

    assert offenders == []
