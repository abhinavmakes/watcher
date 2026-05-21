CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL CHECK (source IN ('hn', 'rss', 'github', 'producthunt')),
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  canonical_url TEXT NOT NULL,
  content TEXT,
  published_at TIMESTAMPTZ,
  domains TEXT[] DEFAULT '{}',
  relevance FLOAT DEFAULT 0.0,
  is_noise BOOLEAN DEFAULT false,
  embedding VECTOR(768),
  source_meta JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX idx_articles_canonical_url ON articles (canonical_url);
CREATE INDEX idx_articles_source ON articles (source);
CREATE INDEX idx_articles_created ON articles (created_at DESC);
CREATE INDEX idx_articles_embedding ON articles
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE clusters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  summary TEXT,
  so_what TEXT,
  momentum_score FLOAT DEFAULT 0.0,
  article_count INT DEFAULT 0,
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'stale')),
  signal_type TEXT DEFAULT 'cluster' CHECK (signal_type IN ('cluster', 'single_source')),
  key_entities TEXT[] DEFAULT '{}',
  domains TEXT[] DEFAULT '{}',
  centroid VECTOR(768),
  first_seen_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_clusters_momentum ON clusters (momentum_score DESC);
CREATE INDEX idx_clusters_status ON clusters (status);

CREATE TABLE cluster_articles (
  cluster_id UUID REFERENCES clusters(id) ON DELETE CASCADE,
  article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
  added_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (cluster_id, article_id)
);

CREATE TABLE user_preferences (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  interests TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own prefs" ON user_preferences
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users write own prefs" ON user_preferences
  FOR ALL USING (auth.uid() = user_id);

CREATE TABLE user_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL CHECK (provider IN ('openai', 'anthropic', 'google')),
  model TEXT NOT NULL,
  key_hash TEXT NOT NULL,
  encrypted_key BYTEA NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, provider)
);

ALTER TABLE user_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own keys" ON user_keys
  FOR ALL USING (auth.uid() = user_id);

CREATE TABLE pipeline_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
  articles_fetched INT DEFAULT 0,
  articles_classified INT DEFAULT 0,
  clusters_updated INT DEFAULT 0,
  clusters_created INT DEFAULT 0,
  source_stats JSONB DEFAULT '{}',
  error_message TEXT
);

CREATE INDEX idx_pipeline_runs_status ON pipeline_runs (completed_at DESC);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_clusters_updated_at
BEFORE UPDATE ON clusters
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_user_preferences_updated_at
BEFORE UPDATE ON user_preferences
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
