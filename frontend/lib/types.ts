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

export type RunStatus = "running" | "completed" | "failed";

export interface RunSummary {
  id: string;
  started_at: string;
  completed_at: string | null;
  status: RunStatus;
  articles_fetched: number;
  articles_classified: number;
  clusters_created: number;
  clusters_updated: number;
  cost_usd: number;
  tokens_in: number;
  tokens_out: number;
  stage_timings: Record<string, number>;
  error_message?: string | null;
}

export interface RunPage {
  runs: RunSummary[];
}
