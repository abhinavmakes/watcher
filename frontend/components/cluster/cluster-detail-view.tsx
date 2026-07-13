"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { DomainTag } from "@/components/domain-tag";
import { MomentumReadout } from "@/components/feed/momentum-readout";
import { ApiError, RateLimitError } from "@/lib/api";
import { momentumColor } from "@/lib/momentum";
import type { ClusterDetail } from "@/lib/types";
import { useCluster } from "@/hooks/use-cluster";

import { ArticleList } from "./article-list";
import {
  DetailError,
  DetailNotFound,
  DetailRateLimited,
  DetailSkeleton,
} from "./detail-states";

function DetailHeader() {
  return (
    <div className="flex items-center justify-between border-b border-border/60 pb-4">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        Briefing
      </Link>
      <Link
        href="/"
        className="font-mono text-sm font-semibold tracking-[0.25em] text-foreground"
      >
        WATCHER
      </Link>
    </div>
  );
}

function DetailBody({ detail }: { detail: ClusterDetail }) {
  const heat = momentumColor(detail.momentum);
  const hasSoWhat = Boolean(detail.so_what);
  const signal = detail.so_what ?? detail.summary ?? null;
  const showSummary = hasSoWhat && Boolean(detail.summary);

  return (
    <article className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1">
          {detail.domains.map((domain) => (
            <DomainTag key={domain} domain={domain} />
          ))}
        </div>
        <MomentumReadout value={detail.momentum} size="lg" />
      </div>

      <h1 className="text-2xl font-semibold leading-tight text-pretty sm:text-3xl">
        {detail.title}
      </h1>

      {signal && (
        <div
          className="flex flex-col gap-2 border-l-2 pl-4"
          style={{ borderColor: momentumColor(detail.momentum, 0.7) }}
        >
          <span
            className="font-mono text-[10px] uppercase tracking-[0.18em]"
            style={{ color: heat }}
          >
            {hasSoWhat ? "Signal" : "Summary"}
          </span>
          <p className="text-pretty text-lg leading-snug text-foreground">{signal}</p>
        </div>
      )}

      {showSummary && (
        <p className="text-pretty leading-relaxed text-muted-foreground">
          {detail.summary}
        </p>
      )}

      {detail.key_entities.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {detail.key_entities.map((entity) => (
            <span
              key={entity}
              className="rounded-full bg-muted px-2.5 py-0.5 font-mono text-[11px] text-muted-foreground"
            >
              {entity}
            </span>
          ))}
        </div>
      )}

      <hr className="border-border/50" />

      <ArticleList articles={detail.articles} />
    </article>
  );
}

export function ClusterDetailView({ id }: { id: string }) {
  const { detail, error, isLoading } = useCluster(id);

  useEffect(() => {
    if (error instanceof RateLimitError) {
      toast.warning("Slow down", {
        description: `You're being rate limited. Try again in ${error.retryAfterSeconds}s.`,
      });
    }
  }, [error]);

  const notFound = error instanceof ApiError && error.status === 404;

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12">
      <DetailHeader />
      {isLoading ? (
        <DetailSkeleton />
      ) : error instanceof RateLimitError ? (
        <DetailRateLimited retryAfterSeconds={error.retryAfterSeconds} />
      ) : notFound ? (
        <DetailNotFound />
      ) : error ? (
        <DetailError />
      ) : detail ? (
        <DetailBody detail={detail} />
      ) : (
        <DetailNotFound />
      )}
    </div>
  );
}
