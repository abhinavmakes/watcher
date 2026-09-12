import type { RunStatus, RunSummary } from "@/lib/types";

const STATUS_DOT: Record<RunStatus, string> = {
  completed: "bg-emerald-600",
  failed: "bg-red-600",
  running: "bg-amber-500",
};

function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const minutes = Math.round((Date.now() - then) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function formatDuration(startedAt: string, completedAt: string | null): string | null {
  if (!completedAt) return null;
  const ms = new Date(completedAt).getTime() - new Date(startedAt).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

function formatCost(usd: number): string {
  if (usd <= 0) return "$0.00";
  if (usd < 0.01) return "<$0.01";
  return `$${usd.toFixed(2)}`;
}

export function LastRunStrip({ run }: { run: RunSummary }) {
  const timestamp = run.completed_at ?? run.started_at;
  const duration = formatDuration(run.started_at, run.completed_at);
  const parts = [
    `${run.articles_fetched} articles`,
    `${run.clusters_created} new stories`,
    duration,
    formatCost(run.cost_usd),
  ].filter(Boolean);

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <span className={`size-1.5 rounded-full ${STATUS_DOT[run.status]}`} />
        Last run {formatRelativeTime(timestamp)}
      </span>
      {parts.map((part) => (
        <span key={part} className="inline-flex items-center gap-2">
          <span aria-hidden className="text-border">
            ·
          </span>
          <span className="tabular-nums">{part}</span>
        </span>
      ))}
      {run.status === "failed" && (
        <span className="text-destructive">{run.error_message ?? "Run failed"}</span>
      )}
    </div>
  );
}
