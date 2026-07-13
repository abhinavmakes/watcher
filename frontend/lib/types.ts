export type ClusterStatus = "active" | "stale";

export interface ClusterCard {
  id: string;
  title: string;
  summary?: string | null;
  so_what?: string | null;
  momentum: number;
  domains: string[];
  key_entities: string[];
  article_count: number;
  status: ClusterStatus;
}

export interface ClusterPage {
  cards: ClusterCard[];
  total: number;
  limit: number;
  offset: number;
}

export interface ClusterArticleRef {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at?: string | null;
}

export interface ClusterDetail extends ClusterCard {
  articles: ClusterArticleRef[];
}
