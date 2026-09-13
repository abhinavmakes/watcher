from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.core.supabase import SupabaseGateway
from app.models.article import EmbeddedArticle
from app.models.classification import ArticleDomain
from app.models.cluster import Cluster, ClusterResult, ExistingCluster
from app.models.synthesis import SynthesisOutput
from app.services.cluster_store import (
    _parse_vector,
    _update_centroid,
    fetch_active_cluster_arrivals,
    fetch_cluster_detail,
    fetch_clusters_page,
    fetch_existing_clusters,
    persist_cluster_result,
    update_cluster_momentum,
)


def _card_row(cluster_id: str = "c1", status: str = "active") -> dict[str, Any]:
    return {
        "id": cluster_id,
        "title": "Anthropic ships a 1M-token context window",
        "summary": None,
        "so_what": None,
        "momentum_score": 5.0,
        "domains": ["llms"],
        "key_entities": ["anthropic"],
        "article_count": 3,
        "status": status,
    }


class RecordingQuery:
    def __init__(
        self,
        table: str,
        recorder: list[Any],
        responses: dict[tuple[str, str], Any],
        counts: dict[tuple[str, str], int],
    ):
        self._table = table
        self._rec = recorder
        self._responses = responses
        self._counts = counts
        self._op = "select"
        self._payload: Any = None
        self._filters: dict[str, Any] = {}
        self._on_conflict: str | None = None
        self._order: tuple[str, bool] | None = None
        self._range: tuple[int, int] | None = None
        self._contains: dict[str, Any] = {}

    def select(self, columns: str, count: str | None = None) -> "RecordingQuery":
        self._op = "select"
        return self

    def contains(self, column: str, values: Any) -> "RecordingQuery":
        self._contains[column] = values
        return self

    def order(self, column: str, desc: bool = False) -> "RecordingQuery":
        self._order = (column, desc)
        return self

    def range(self, start: int, end: int) -> "RecordingQuery":
        self._range = (start, end)
        return self

    def eq(self, column: str, value: Any) -> "RecordingQuery":
        self._filters[column] = value
        return self

    def in_(self, column: str, values: list[str]) -> "RecordingQuery":
        self._filters[column] = list(values)
        return self

    def insert(self, row: dict[str, Any]) -> "RecordingQuery":
        self._op = "insert"
        self._payload = row
        return self

    def update(self, row: dict[str, Any]) -> "RecordingQuery":
        self._op = "update"
        self._payload = row
        return self

    def upsert(
        self, rows: list[dict[str, Any]], *, on_conflict: str, ignore_duplicates: bool
    ) -> "RecordingQuery":
        self._op = "upsert"
        self._payload = rows
        self._on_conflict = on_conflict
        return self

    async def execute(self) -> SimpleNamespace:
        self._rec.append(
            SimpleNamespace(
                table=self._table,
                op=self._op,
                payload=self._payload,
                filters=self._filters,
                on_conflict=self._on_conflict,
                order=self._order,
                range=self._range,
                contains=self._contains,
            )
        )
        return SimpleNamespace(
            data=self._responses.get((self._table, self._op), []),
            count=self._counts.get((self._table, self._op)),
        )


class RecordingGateway:
    def __init__(
        self,
        responses: dict[tuple[str, str], Any] | None = None,
        counts: dict[tuple[str, str], int] | None = None,
    ) -> None:
        self.calls: list[Any] = []
        self._responses = responses or {}
        self._counts = counts or {}

    def table(self, table_name: str) -> RecordingQuery:
        return RecordingQuery(table_name, self.calls, self._responses, self._counts)


def _embedded(
    url: str, vector: list[float], relevance: float, key_entities: list[str] | None = None
) -> EmbeddedArticle:
    return EmbeddedArticle(
        canonical_url=url,
        title=f"{url} title",
        domains=[ArticleDomain.LLMS],
        key_entities=key_entities or [],
        relevance=relevance,
        vector=vector,
    )


def test_parse_vector_handles_string_and_list() -> None:
    assert _parse_vector("[1.0, 2.0, 3.0]") == [1.0, 2.0, 3.0]
    assert _parse_vector([1, 2, 3]) == [1.0, 2.0, 3.0]


def test_update_centroid_is_weighted_running_mean() -> None:
    new_centroid, new_count = _update_centroid([0.0, 0.0, 1.0], 2, [[0.0, 0.5, 1.0]])

    assert new_centroid == pytest.approx([0.0, 1 / 6, 1.0])
    assert new_count == 3


@pytest.mark.asyncio
async def test_fetch_existing_clusters_parses_and_skips_null_centroid() -> None:
    gateway = RecordingGateway(
        {
            ("clusters", "select"): [
                {
                    "id": "c1",
                    "centroid": "[0.1, 0.2, 0.3]",
                    "article_count": 4,
                    "key_entities": ["anthropic"],
                },
                {"id": "c2", "centroid": None, "article_count": 1, "key_entities": []},
            ]
        }
    )

    clusters = await fetch_existing_clusters(cast(SupabaseGateway, gateway))

    assert clusters == [
        ExistingCluster(
            id="c1", centroid=[0.1, 0.2, 0.3], article_count=4, key_entities=["anthropic"]
        )
    ]
    assert gateway.calls[0].table == "clusters"
    assert gateway.calls[0].filters == {"status": "active"}


@pytest.mark.asyncio
async def test_persist_inserts_new_clusters_and_updates_existing() -> None:
    gateway = RecordingGateway(
        {
            ("articles", "select"): [
                {"id": "aid", "canonical_url": "a"},
                {"id": "bid", "canonical_url": "b"},
                {"id": "did", "canonical_url": "d"},
            ],
            ("clusters", "insert"): [{"id": "new-1"}],
        }
    )
    result = ClusterResult(
        new_clusters=[
            Cluster(
                centroid=[1.0, 0.25, 0.0],
                member_urls=["a", "b"],
                domains=[ArticleDomain.AI_AGENTS, ArticleDomain.LLMS],
                key_entities=["amazon", "anthropic"],
            )
        ],
        updated={"existing-1": ["d"]},
        orphans=["c"],
    )
    existing = [
        ExistingCluster(
            id="existing-1", centroid=[0.0, 0.0, 1.0], article_count=2, key_entities=["anthropic"]
        )
    ]
    embedded = [
        _embedded("a", [1.0, 0.0, 0.0], relevance=0.9),
        _embedded("b", [1.0, 0.5, 0.0], relevance=0.5),
        _embedded("d", [0.0, 0.5, 1.0], relevance=0.7, key_entities=["fable"]),
    ]

    await persist_cluster_result(cast(SupabaseGateway, gateway), result, existing, embedded)

    def by(table: str, op: str) -> list[Any]:
        return [c for c in gateway.calls if c.table == table and c.op == op]

    # url -> id resolution covers every new + updated member, not orphans.
    article_select = by("articles", "select")[0]
    assert article_select.filters == {"canonical_url": ["a", "b", "d"]}

    # New cluster: title from the highest-relevance member (a, 0.9), provisional signal_type.
    insert = by("clusters", "insert")[0]
    assert insert.payload["title"] == "a title"
    assert insert.payload["centroid"] == [1.0, 0.25, 0.0]
    assert insert.payload["domains"] == ["ai_agents", "llms"]
    assert insert.payload["article_count"] == 2
    assert insert.payload["signal_type"] == "cluster"
    assert insert.payload["key_entities"] == ["amazon", "anthropic"]

    # Existing cluster: centroid recomputed via running mean, count bumped.
    update = by("clusters", "update")[0]
    assert update.filters == {"id": "existing-1"}
    assert update.payload["centroid"] == pytest.approx([0.0, 1 / 6, 1.0])
    assert update.payload["article_count"] == 3
    assert update.payload["key_entities"] == ["anthropic", "fable"]

    # cluster_articles links by resolved article_id, idempotent on the composite PK.
    link_payloads = [c.payload for c in by("cluster_articles", "upsert")]
    assert {"cluster_id": "new-1", "article_id": "aid"} in link_payloads[0]
    assert {"cluster_id": "new-1", "article_id": "bid"} in link_payloads[0]
    assert link_payloads[1] == [{"cluster_id": "existing-1", "article_id": "did"}]
    assert by("cluster_articles", "upsert")[0].on_conflict == "cluster_id,article_id"


@pytest.mark.asyncio
async def test_persist_writes_synthesis_onto_new_cluster() -> None:
    gateway = RecordingGateway(
        {
            ("articles", "select"): [
                {"id": "aid", "canonical_url": "a"},
                {"id": "bid", "canonical_url": "b"},
            ],
            ("clusters", "insert"): [{"id": "new-1"}],
        }
    )
    result = ClusterResult(
        new_clusters=[
            Cluster(
                centroid=[1.0, 0.0, 0.0],
                member_urls=["a", "b"],
                domains=[ArticleDomain.LLMS],
                key_entities=["anthropic"],
            )
        ],
        updated={},
        orphans=[],
    )
    embedded = [
        _embedded("a", [1.0, 0.0, 0.0], relevance=0.9),
        _embedded("b", [1.0, 0.5, 0.0], relevance=0.5),
    ]
    synthesis = SynthesisOutput(
        title="Anthropic ships a 1M-token context window",
        summary="Anthropic released a 1M-token Claude model at standard pricing.",
        so_what="Revisit whether your RAG layer still earns its complexity.",
    )

    await persist_cluster_result(cast(SupabaseGateway, gateway), result, [], embedded, [synthesis])

    insert = next(c for c in gateway.calls if c.table == "clusters" and c.op == "insert")
    # Synthesis title overrides the member-headline fallback; summary/so_what are written.
    assert insert.payload["title"] == "Anthropic ships a 1M-token context window"
    assert insert.payload["summary"] == synthesis.summary
    assert insert.payload["so_what"] == synthesis.so_what
    assert insert.payload["signal_type"] == "cluster"


@pytest.mark.asyncio
async def test_persist_falls_back_to_member_title_when_synthesis_missing() -> None:
    gateway = RecordingGateway(
        {
            ("articles", "select"): [{"id": "aid", "canonical_url": "a"}],
            ("clusters", "insert"): [{"id": "new-1"}],
        }
    )
    result = ClusterResult(
        new_clusters=[
            Cluster(
                centroid=[1.0, 0.0, 0.0],
                member_urls=["a", "b"],
                domains=[ArticleDomain.LLMS],
                key_entities=["anthropic"],
            )
        ],
        updated={},
        orphans=[],
    )
    embedded = [
        _embedded("a", [1.0, 0.0, 0.0], relevance=0.9),
        _embedded("b", [1.0, 0.5, 0.0], relevance=0.5),
    ]

    # synthesis is None for this cluster (failed/skipped) -> fall back, no summary/so_what.
    await persist_cluster_result(cast(SupabaseGateway, gateway), result, [], embedded, [None])

    insert = next(c for c in gateway.calls if c.table == "clusters" and c.op == "insert")
    assert insert.payload["title"] == "a title"
    assert "summary" not in insert.payload
    assert "so_what" not in insert.payload


@pytest.mark.asyncio
async def test_persist_is_a_noop_when_nothing_to_link() -> None:
    gateway = RecordingGateway()
    result = ClusterResult(new_clusters=[], updated={}, orphans=["c", "d"])

    await persist_cluster_result(cast(SupabaseGateway, gateway), result, [], [])

    assert gateway.calls == []


@pytest.mark.asyncio
async def test_fetch_active_cluster_arrivals_groups_added_at_by_cluster() -> None:
    gateway = RecordingGateway(
        {
            ("clusters", "select"): [{"id": "c1"}, {"id": "c2"}],
            ("cluster_articles", "select"): [
                {"cluster_id": "c1", "added_at": "2026-06-25T10:00:00+00:00"},
                {"cluster_id": "c1", "added_at": "2026-06-25T08:00:00+00:00"},
                {"cluster_id": "c2", "added_at": "2026-06-24T10:00:00+00:00"},
            ],
        }
    )

    arrivals = await fetch_active_cluster_arrivals(cast(SupabaseGateway, gateway))

    assert arrivals == {
        "c1": [
            datetime(2026, 6, 25, 10, tzinfo=UTC),
            datetime(2026, 6, 25, 8, tzinfo=UTC),
        ],
        "c2": [datetime(2026, 6, 24, 10, tzinfo=UTC)],
    }
    # Only active clusters are scanned, then their members are pulled by cluster_id.
    assert gateway.calls[0].filters == {"status": "active"}
    assert gateway.calls[1].filters == {"cluster_id": ["c1", "c2"]}


@pytest.mark.asyncio
async def test_fetch_active_cluster_arrivals_uses_earlier_of_published_and_added() -> None:
    gateway = RecordingGateway(
        {
            ("clusters", "select"): [{"id": "c1"}],
            ("cluster_articles", "select"): [
                # published earlier than added -> published_at wins (late-ingested archive post)
                {
                    "cluster_id": "c1",
                    "added_at": "2026-06-25T10:00:00+00:00",
                    "articles": {"published_at": "2026-06-01T00:00:00+00:00"},
                },
                # published later than added -> added_at wins (feed timezone bug)
                {
                    "cluster_id": "c1",
                    "added_at": "2026-06-25T10:00:00+00:00",
                    "articles": {"published_at": "2026-06-26T00:00:00+00:00"},
                },
                # no article relation -> added_at
                {"cluster_id": "c1", "added_at": "2026-06-25T08:00:00+00:00", "articles": None},
            ],
        }
    )

    arrivals = await fetch_active_cluster_arrivals(cast(SupabaseGateway, gateway))

    assert arrivals == {
        "c1": [
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 6, 25, 10, tzinfo=UTC),
            datetime(2026, 6, 25, 8, tzinfo=UTC),
        ]
    }


@pytest.mark.asyncio
async def test_fetch_active_cluster_arrivals_keeps_memberless_clusters() -> None:
    gateway = RecordingGateway(
        {("clusters", "select"): [{"id": "c1"}], ("cluster_articles", "select"): []}
    )

    arrivals = await fetch_active_cluster_arrivals(cast(SupabaseGateway, gateway))

    assert arrivals == {"c1": []}


@pytest.mark.asyncio
async def test_update_cluster_momentum_writes_score_and_status() -> None:
    gateway = RecordingGateway()

    await update_cluster_momentum(
        cast(SupabaseGateway, gateway), "c1", momentum_score=3.5, status="stale"
    )

    update = gateway.calls[0]
    assert update.table == "clusters"
    assert update.op == "update"
    assert update.payload == {"momentum_score": 3.5, "status": "stale"}
    assert update.filters == {"id": "c1"}


@pytest.mark.asyncio
async def test_fetch_clusters_page_hides_stale_orders_by_raw_and_paginates() -> None:
    row = _card_row()
    gateway = RecordingGateway({("clusters", "select"): [row]}, counts={("clusters", "select"): 1})

    rows, total = await fetch_clusters_page(
        cast(SupabaseGateway, gateway), limit=20, offset=0, domain=None
    )

    assert rows == [row]
    assert total == 1  # the filtered count, not len(page)
    call = gateway.calls[0]
    assert call.filters == {"status": "active"}  # stale hidden at the store
    assert call.order == ("momentum_score", True)  # raw score DESC (indexed)
    assert call.range == (0, 19)  # postgREST range end is inclusive


@pytest.mark.asyncio
async def test_fetch_clusters_page_filters_by_domain_when_given() -> None:
    gateway = RecordingGateway({("clusters", "select"): []}, counts={("clusters", "select"): 0})

    await fetch_clusters_page(cast(SupabaseGateway, gateway), limit=10, offset=0, domain="llms")

    assert gateway.calls[0].contains == {"domains": ["llms"]}  # array superset match


@pytest.mark.asyncio
async def test_fetch_cluster_detail_returns_none_for_unknown_id() -> None:
    gateway = RecordingGateway({("clusters", "select"): []})

    result = await fetch_cluster_detail(cast(SupabaseGateway, gateway), "nope")

    assert result is None
    assert len(gateway.calls) == 1  # short-circuits before any member queries
    assert gateway.calls[0].filters == {"id": "nope"}


@pytest.mark.asyncio
async def test_fetch_cluster_detail_joins_members_and_ignores_status() -> None:
    cluster_row = _card_row(status="stale")  # stale, yet still resolves by direct id
    article_row = {"id": "a1", "title": "at", "url": "u", "source": "hn", "published_at": None}
    gateway = RecordingGateway(
        {
            ("clusters", "select"): [cluster_row],
            ("cluster_articles", "select"): [{"article_id": "a1"}],
            ("articles", "select"): [article_row],
        }
    )

    result = await fetch_cluster_detail(cast(SupabaseGateway, gateway), "c1")

    assert result == (cluster_row, [article_row])
    # cluster fetched by id with NO status filter -> a stale permalink still resolves.
    assert gateway.calls[0].filters == {"id": "c1"}
    # members: link table by cluster_id, then articles by resolved id.
    assert gateway.calls[1].filters == {"cluster_id": "c1"}
    assert gateway.calls[2].filters == {"id": ["a1"]}


@pytest.mark.asyncio
async def test_fetch_cluster_detail_skips_article_query_when_memberless() -> None:
    gateway = RecordingGateway(
        {("clusters", "select"): [_card_row()], ("cluster_articles", "select"): []}
    )

    result = await fetch_cluster_detail(cast(SupabaseGateway, gateway), "c1")

    assert result == (_card_row(), [])
    assert len(gateway.calls) == 2  # no articles query when there are no members
