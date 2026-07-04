"use client";

import { Clock, Inbox, TriangleAlert } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";

function CardSkeleton({ minHeight }: { minHeight: string }) {
  return (
    <div
      className={`flex flex-col gap-4 rounded-xl border border-border/60 bg-card/50 p-5 ${minHeight}`}
    >
      <div className="flex items-start justify-between">
        <Skeleton className="mt-1 h-3 w-28" />
        <Skeleton className="h-9 w-12" />
      </div>
      <Skeleton className="h-4 w-full" />
      <div className="flex flex-col gap-2 border-l-2 border-border pl-3">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-5/6" />
      </div>
      <div className="mt-auto flex justify-between border-t border-border/50 pt-3">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-3 w-10" />
      </div>
    </div>
  );
}

export function FeedSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CardSkeleton minHeight="min-h-64" />
        <CardSkeleton minHeight="min-h-64" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <CardSkeleton key={index} minHeight="min-h-52" />
        ))}
      </div>
    </div>
  );
}

function StatePanel({
  icon,
  title,
  children,
  tone = "muted",
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  tone?: "muted" | "error";
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed py-24 text-center ${
        tone === "error" ? "border-destructive/40" : "border-border"
      }`}
    >
      {icon}
      <h2 className="text-lg font-medium">{title}</h2>
      <div className="max-w-sm text-sm text-muted-foreground">{children}</div>
    </div>
  );
}

export function FeedEmpty() {
  return (
    <StatePanel
      icon={<Inbox className="size-8 text-muted-foreground" aria-hidden />}
      title="No fresh signal yet"
    >
      Watcher updates once a day and hides stale clusters. When the next daily run
      completes, the day&apos;s briefing shows up here.
    </StatePanel>
  );
}

export function FeedError({ onRetry }: { onRetry: () => void }) {
  return (
    <StatePanel
      tone="error"
      icon={<TriangleAlert className="size-8 text-destructive" aria-hidden />}
      title="Couldn't load the feed"
    >
      <p>Something went wrong reaching the API. Check your connection and try again.</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
      >
        Try again
      </button>
    </StatePanel>
  );
}

export function FeedRateLimited({
  retryAfterSeconds,
  onRetry,
}: {
  retryAfterSeconds: number;
  onRetry: () => void;
}) {
  return (
    <StatePanel
      icon={<Clock className="size-8 text-muted-foreground" aria-hidden />}
      title="Slow down a moment"
    >
      <p>The feed is temporarily rate limited. Try again in {retryAfterSeconds}s.</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
      >
        Try again
      </button>
    </StatePanel>
  );
}

export function FeedDomainEmpty({ onClear }: { onClear: () => void }) {
  return (
    <StatePanel
      icon={<Inbox className="size-8 text-muted-foreground" aria-hidden />}
      title="Nothing in this domain"
    >
      <button
        type="button"
        onClick={onClear}
        className="mt-2 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
      >
        Clear filter
      </button>
    </StatePanel>
  );
}
