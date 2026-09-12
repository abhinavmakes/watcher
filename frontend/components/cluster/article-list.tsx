import { ExternalLink } from "lucide-react";

import { hostname, isSafeHttpUrl } from "@/lib/links";
import type { ClusterArticleRef } from "@/lib/types";

function formatDate(iso?: string | null): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function ArticleRow({ article }: { article: ClusterArticleRef }) {
  const safe = isSafeHttpUrl(article.url);
  const host = safe ? hostname(article.url) : null;
  const date = formatDate(article.published_at);

  const body = (
    <>
      <div className="flex min-w-0 flex-col gap-1">
        <span className="text-[13px] text-muted-foreground">
          {article.source}
        </span>
        <span className="text-pretty text-sm text-foreground group-hover:underline group-hover:decoration-1 group-hover:underline-offset-2">
          {article.title}
        </span>
        {host && (
          <span className="text-[13px] text-muted-foreground">{host}</span>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2 pt-0.5">
        {date && (
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {date}
          </span>
        )}
        {safe && (
          <ExternalLink
            className="size-3.5 text-muted-foreground transition-colors group-hover:text-foreground"
            aria-hidden
          />
        )}
      </div>
    </>
  );

  if (!safe) {
    return (
      <div className="flex items-start justify-between gap-4 py-3">{body}</div>
    );
  }

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex items-start justify-between gap-4 py-3"
    >
      {body}
    </a>
  );
}

export function ArticleList({ articles }: { articles: ClusterArticleRef[] }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-base font-semibold tracking-tight text-foreground">
        Sources · {articles.length}
      </h2>
      {articles.length === 0 ? (
        <p className="text-sm text-muted-foreground">No source articles recorded.</p>
      ) : (
        <div className="divide-y divide-border/50 border-t border-border/50">
          {articles.map((article) => (
            <ArticleRow key={article.id} article={article} />
          ))}
        </div>
      )}
    </section>
  );
}
