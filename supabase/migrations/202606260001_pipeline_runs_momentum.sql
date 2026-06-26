-- Record momentum-stage health per run: how many active clusters were re-scored and
-- how many crossed the staleness line, so a run's freshness sweep is auditable.
ALTER TABLE pipeline_runs
  ADD COLUMN clusters_scored INT DEFAULT 0,
  ADD COLUMN clusters_stale INT DEFAULT 0;
