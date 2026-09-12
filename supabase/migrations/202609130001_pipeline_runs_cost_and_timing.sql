-- Additive, defaulted, no backfill: the pipeline could not previously state what a
-- run costs. cost_usd/tokens_in/tokens_out come from PydanticAI's per-call usage
-- totals; stage_timings is per-stage wall time in seconds.
-- DOUBLE PRECISION, not NUMERIC: postgREST returns NUMERIC as a JSON string to preserve
-- arbitrary precision, which a dollar-and-cents display doesn't need and Pydantic would
-- otherwise have to coerce on every read.
ALTER TABLE pipeline_runs
  ADD COLUMN cost_usd DOUBLE PRECISION DEFAULT 0,
  ADD COLUMN tokens_in INT DEFAULT 0,
  ADD COLUMN tokens_out INT DEFAULT 0,
  ADD COLUMN stage_timings JSONB DEFAULT '{}';
