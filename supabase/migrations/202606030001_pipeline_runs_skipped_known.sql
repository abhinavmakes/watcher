-- Track how many fetched articles were skipped because they were already
-- persisted (dedup-before-classify), so the audit trail shows the LLM-cost saving.
ALTER TABLE pipeline_runs
  ADD COLUMN articles_skipped_known INT DEFAULT 0;
