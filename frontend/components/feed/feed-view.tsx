"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { DomainFilter } from "@/components/feed/domain-filter";
import { FeedGrid } from "@/components/feed/feed-grid";
import {
  FeedDomainEmpty,
  FeedEmpty,
  FeedError,
  FeedRateLimited,
  FeedSkeleton,
} from "@/components/feed/feed-states";
import { LastRunStrip } from "@/components/feed/last-run-strip";
import { useClusters } from "@/hooks/use-clusters";
import { useLatestRun } from "@/hooks/use-latest-run";
import { RateLimitError } from "@/lib/api";
import type { ClusterPage } from "@/lib/types";

function FeedStatus({
  total,
  domainCount,
}: {
  total: number;
  domainCount: number;
}) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[13px] text-muted-foreground">
      <span className="tabular-nums text-foreground">
        {total} {total === 1 ? "story" : "stories"}
      </span>
      <span aria-hidden className="text-border">·</span>
      <span className="tabular-nums">{domainCount} topics</span>
      <span aria-hidden className="text-border">·</span>
      <span>updated weekly</span>
    </div>
  );
}

export function FeedView({ initialData }: { initialData?: ClusterPage }) {
  const { page, error, isLoading, refresh } = useClusters(initialData);
  const { run } = useLatestRun();
  const [activeDomain, setActiveDomain] = useState<string | null>(null);

  useEffect(() => {
    if (error instanceof RateLimitError) {
      toast.warning("Slow down", {
        description: `You're being rate limited. Try again in ${error.retryAfterSeconds}s.`,
      });
    }
  }, [error]);

  const cards = useMemo(() => page?.cards ?? [], [page]);

  const domains = useMemo(() => {
    const seen = new Set<string>();
    for (const card of cards) {
      for (const domain of card.domains) seen.add(domain);
    }
    return [...seen];
  }, [cards]);

  const visible = useMemo(
    () =>
      activeDomain
        ? cards.filter((card) => card.domains.includes(activeDomain))
        : cards,
    [cards, activeDomain],
  );

  return (
    <section className="flex flex-col gap-6">
      <FeedStatus
        total={page?.total ?? cards.length}
        domainCount={domains.length}
      />
      {run && <LastRunStrip run={run} />}

      {isLoading && !page ? (
        <FeedSkeleton />
      ) : error instanceof RateLimitError ? (
        <FeedRateLimited
          retryAfterSeconds={error.retryAfterSeconds}
          onRetry={refresh}
        />
      ) : error ? (
        <FeedError onRetry={refresh} />
      ) : cards.length === 0 ? (
        <FeedEmpty />
      ) : (
        <div className="flex flex-col gap-6">
          <DomainFilter
            domains={domains}
            active={activeDomain}
            onSelect={setActiveDomain}
          />
          {visible.length === 0 ? (
            <FeedDomainEmpty onClear={() => setActiveDomain(null)} />
          ) : (
            <FeedGrid cards={visible} />
          )}
        </div>
      )}
    </section>
  );
}
