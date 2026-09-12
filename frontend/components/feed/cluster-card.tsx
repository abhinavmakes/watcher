import Link from "next/link";

import { domainMeta } from "@/lib/domains";
import { momentumColor } from "@/lib/momentum";
import type { ClusterCard as ClusterCardModel } from "@/lib/types";

import { MomentumReadout } from "./momentum-readout";

type CardVariant = "feature" | "standard";

export function ClusterCard({
  card,
  variant = "standard",
}: {
  card: ClusterCardModel;
  variant?: CardVariant;
}) {
  const isFeature = variant === "feature";
  const signal = card.so_what ?? card.summary ?? null;
  const domains = card.domains
    .slice(0, isFeature ? 3 : 2)
    .map((domain) => domainMeta(domain).label);

  return (
    <Link
      href={`/cluster/${card.id}`}
      className="card-surface group flex h-full flex-col gap-3 rounded-lg p-5 transition-shadow duration-200 hover:card-surface-hover sm:p-6"
    >
      <div className="flex items-start justify-between gap-4">
        <h3
          className={`font-semibold tracking-tight text-pretty text-foreground ${
            isFeature ? "text-xl leading-snug" : "line-clamp-3 text-base leading-snug"
          }`}
        >
          {card.title}
        </h3>
        <MomentumReadout value={card.momentum} size={isFeature ? "lg" : "md"} />
      </div>

      {signal && (
        <p
          className={`text-pretty leading-relaxed text-muted-foreground ${
            isFeature ? "line-clamp-4 text-[15px]" : "line-clamp-3 text-sm"
          }`}
        >
          {signal}
        </p>
      )}

      <div className="mt-auto flex items-center gap-2 pt-3 text-[13px] text-muted-foreground">
        <span className="truncate">{domains.join(" · ")}</span>
        <span aria-hidden className="text-border">
          ·
        </span>
        <span className="shrink-0 tabular-nums">
          {card.article_count} {card.article_count === 1 ? "source" : "sources"}
        </span>
        <span
          aria-hidden
          className="ml-auto shrink-0 text-border transition-transform duration-200 group-hover:translate-x-0.5"
          style={{ color: momentumColor(card.momentum, 0.35) }}
        >
          →
        </span>
      </div>
    </Link>
  );
}
