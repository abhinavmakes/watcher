"use client";

import Link from "next/link";
import { Clock, FileQuestion, TriangleAlert } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";

export function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <Skeleton className="mt-1 h-3 w-40" />
        <Skeleton className="h-14 w-16" />
      </div>
      <Skeleton className="h-8 w-4/5" />
      <div className="flex flex-col gap-2 border-l-2 border-border pl-4">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-11/12" />
      </div>
      <div className="flex flex-col gap-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-3/4" />
      </div>
      <div className="mt-2 flex flex-col gap-4">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="flex flex-col gap-1.5">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ))}
      </div>
    </div>
  );
}

function DetailPanel({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      {icon}
      <h1 className="text-lg font-medium">{title}</h1>
      <p className="max-w-sm text-sm text-muted-foreground">{children}</p>
      <Link
        href="/"
        className="mt-2 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
      >
        Back to briefing
      </Link>
    </div>
  );
}

export function DetailNotFound() {
  return (
    <DetailPanel
      icon={<FileQuestion className="size-8 text-muted-foreground" aria-hidden />}
      title="Cluster not found"
    >
      This story isn&apos;t in the briefing — it may have gone stale, or the link is
      wrong.
    </DetailPanel>
  );
}

export function DetailError() {
  return (
    <DetailPanel
      icon={<TriangleAlert className="size-8 text-destructive" aria-hidden />}
      title="Couldn't load this cluster"
    >
      Something went wrong reaching the API. Head back and try again.
    </DetailPanel>
  );
}

export function DetailRateLimited({
  retryAfterSeconds,
}: {
  retryAfterSeconds: number;
}) {
  return (
    <DetailPanel
      icon={<Clock className="size-8 text-muted-foreground" aria-hidden />}
      title="Slow down a moment"
    >
      This page is temporarily rate limited. Try again in {retryAfterSeconds}s.
    </DetailPanel>
  );
}
