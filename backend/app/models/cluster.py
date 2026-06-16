from pydantic import BaseModel, Field

from app.models.classification import ArticleDomain


class Cluster(BaseModel):
    centroid: list[float]
    member_urls: list[str]
    domains: list[ArticleDomain]
    key_entities: list[str] = Field(default_factory=list)


class ExistingCluster(BaseModel):
    id: str
    centroid: list[float]
    article_count: int
    key_entities: list[str] = Field(default_factory=list)


class ClusterResult(BaseModel):
    new_clusters: list[Cluster]
    updated: dict[str, list[str]]  # {existing_cluster_id: [canonical_urls that joined it this run]}
    orphans: list[str]
