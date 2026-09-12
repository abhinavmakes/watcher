-- RLS was enabled only on the two vestigial auth tables. These four carry all live data and
-- had none. No policies are added deliberately: RLS with zero policies denies every role that
-- does not bypass it, and the backend connects as service_role (which does), so the worker and
-- the read API are unaffected. Anything reaching these tables with the publishable/anon key is
-- by definition not this application.
ALTER TABLE articles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE clusters         ENABLE ROW LEVEL SECURITY;
ALTER TABLE cluster_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs    ENABLE ROW LEVEL SECURITY;
