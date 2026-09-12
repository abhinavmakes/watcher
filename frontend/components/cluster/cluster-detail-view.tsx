"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { DomainTag } from "@/components/domain-tag";
import { MomentumReadout } from "@/components/feed/momentum-readout";
import { ApiError, RateLimitError } from "@/lib/api";
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
    <div className="flex items-center justify-between border-b border-border pb-4">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        Back to the briefing
      </Link>
      <Link
        href="/"
        className="text-[15px] font-semibold tracking-tight text-foreground"
      >
        Watcher
      </Link>
    </div>
  );
}

function DetailBody({ detail }: { detail: ClusterDetail }) {
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
        <p className="text-pretty text-lg leading-relaxed text-foreground">{signal}</p>
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
              className="rounded-full bg-muted px-2.5 py-1 text-[13px] text-muted-foreground"
            >
              {entity}
            </span>
          ))}
        </div>
      )}

      <hr className="border-border" />

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
