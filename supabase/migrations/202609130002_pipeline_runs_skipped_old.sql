-- Articles dropped for being published before the freshness cutoff. Separate from
-- articles_skipped_known so a cold feed backfill is visible as its own number rather
-- than hiding inside the dedup count.
ALTER TABLE pipeline_runs
  ADD COLUMN articles_skipped_old INT DEFAULT 0;
