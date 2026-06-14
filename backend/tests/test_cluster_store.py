from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.core.supabase import SupabaseGateway
from app.models.article import EmbeddedArticle
from app.models.classification import ArticleDomain
from app.models.cluster import Cluster, ClusterResult, ExistingCluster
from app.services.cluster_store import (
    _parse_vector,
    _update_centroid,
    fetch_existing_clusters,
    persist_cluster_result,
)


class RecordingQuery:
    def __init__(self, table: str, recorder: list[Any], responses: dict[tuple[str, str], Any]):
        self._table = table
        self._rec = recorder
        self._responses = responses
        self._op = "select"
        self._payload: Any = None
        self._filters: dict[str, Any] = {}
        self._on_conflict: str | None = None

    def select(self, columns: str) -> "RecordingQuery":
        self._op = "select"
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
            )
        )
        return SimpleNamespace(data=self._responses.get((self._table, self._op), []))


class RecordingGateway:
    def __init__(self, responses: dict[tuple[str, str], Any] | None = None) -> None:
        self.calls: list[Any] = []
        self._responses = responses or {}

    def table(self, table_name: str) -> RecordingQuery:
        return RecordingQuery(table_name, self.calls, self._responses)


def _embedded(url: str, vector: list[float], relevance: float) -> EmbeddedArticle:
    return EmbeddedArticle(
        canonical_url=url,
        title=f"{url} title",
        domains=[ArticleDomain.LLMS],
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
                {"id": "c1", "centroid": "[0.1, 0.2, 0.3]", "article_count": 4},
                {"id": "c2", "centroid": None, "article_count": 1},
            ]
        }
    )

    clusters = await fetch_existing_clusters(cast(SupabaseGateway, gateway))

    assert clusters == [ExistingCluster(id="c1", centroid=[0.1, 0.2, 0.3], article_count=4)]
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
            )
        ],
        updated={"existing-1": ["d"]},
        orphans=["c"],
    )
    existing = [ExistingCluster(id="existing-1", centroid=[0.0, 0.0, 1.0], article_count=2)]
    embedded = [
        _embedded("a", [1.0, 0.0, 0.0], relevance=0.9),
        _embedded("b", [1.0, 0.5, 0.0], relevance=0.5),
        _embedded("d", [0.0, 0.5, 1.0], relevance=0.7),
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

    # Existing cluster: centroid recomputed via running mean, count bumped.
    update = by("clusters", "update")[0]
    assert update.filters == {"id": "existing-1"}
    assert update.payload["centroid"] == pytest.approx([0.0, 1 / 6, 1.0])
    assert update.payload["article_count"] == 3

    # cluster_articles links by resolved article_id, idempotent on the composite PK.
    link_payloads = [c.payload for c in by("cluster_articles", "upsert")]
    assert {"cluster_id": "new-1", "article_id": "aid"} in link_payloads[0]
    assert {"cluster_id": "new-1", "article_id": "bid"} in link_payloads[0]
    assert link_payloads[1] == [{"cluster_id": "existing-1", "article_id": "did"}]
    assert by("cluster_articles", "upsert")[0].on_conflict == "cluster_id,article_id"


@pytest.mark.asyncio
async def test_persist_is_a_noop_when_nothing_to_link() -> None:
    gateway = RecordingGateway()
    result = ClusterResult(new_clusters=[], updated={}, orphans=["c", "d"])

    await persist_cluster_result(cast(SupabaseGateway, gateway), result, [], [])

    assert gateway.calls == []
