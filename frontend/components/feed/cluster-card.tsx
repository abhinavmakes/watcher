import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { DomainTag } from "@/components/domain-tag";
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
  const heat = momentumColor(card.momentum);
  const hasSoWhat = Boolean(card.so_what);
  const signal = card.so_what ?? card.summary ?? null;
  const summary = isFeature && hasSoWhat ? card.summary : null;
  const entities = card.key_entities.slice(0, isFeature ? 4 : 2);

  return (
    <Link
      href={`/cluster/${card.id}`}
      className="group flex h-full flex-col gap-4 rounded-xl border border-border/60 bg-card/50 p-5 transition-colors hover:border-border hover:bg-card"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1">
          {card.domains.slice(0, isFeature ? 4 : 3).map((domain) => (
            <DomainTag key={domain} domain={domain} />
          ))}
        </div>
        <MomentumReadout value={card.momentum} size={isFeature ? "lg" : "md"} />
      </div>

      <h3
        className={`font-semibold leading-snug text-pretty text-foreground ${
          isFeature ? "text-xl" : "line-clamp-2 text-base"
        }`}
      >
        {card.title}
      </h3>

      {signal && (
        <div
          className="flex flex-col gap-1.5 border-l-2 pl-3"
          style={{ borderColor: momentumColor(card.momentum, 0.7) }}
        >
          <span
            className="font-mono text-[10px] uppercase tracking-[0.18em]"
            style={{ color: heat }}
          >
            {hasSoWhat ? "Signal" : "Summary"}
          </span>
          <p
            className={`leading-snug text-pretty text-foreground/85 ${
              isFeature ? "text-base" : "line-clamp-3 text-sm"
            }`}
          >
            {signal}
          </p>
        </div>
      )}

      {summary && (
        <p className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">
          {summary}
        </p>
      )}

      <div className="mt-auto flex items-center justify-between gap-3 border-t border-border/50 pt-3 font-mono text-[11px] text-muted-foreground">
        <span className="truncate">{entities.join(" · ") || "—"}</span>
        <span className="inline-flex shrink-0 items-center gap-1 tabular-nums">
          {card.article_count} {card.article_count === 1 ? "source" : "sources"}
          <ArrowRight
            className="size-3 transition-transform group-hover:translate-x-0.5"
            style={{ color: heat }}
            aria-hidden
          />
        </span>
      </div>
    </Link>
  );
}
