import { Fragment } from "react";
import {
  ArrowRight,
  Boxes,
  Filter,
  Gauge,
  Network,
  Rss,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

interface Step {
  label: string;
  desc: string;
  Icon: LucideIcon;
}

const STEPS: Step[] = [
  {
    label: "Fetch",
    desc: "Pull the day's articles from Hacker News and curated RSS feeds.",
    Icon: Rss,
  },
  {
    label: "Classify",
    desc: "Claude Haiku tags each article's domain and relevance, dropping noise.",
    Icon: Filter,
  },
  {
    label: "Embed",
    desc: "Turn each article into a vector so similar stories sit close together.",
    Icon: Boxes,
  },
  {
    label: "Cluster",
    desc: "Entity-anchored grouping merges every source covering the same story.",
    Icon: Network,
  },
  {
    label: "Synthesize",
    desc: "Claude Sonnet writes a factual summary and the “so what” for each cluster.",
    Icon: Sparkles,
  },
  {
    label: "Score",
    desc: "Momentum ranks clusters by how much fresh coverage is converging.",
    Icon: Gauge,
  },
];

export function PipelineFlow() {
  return (
    <ol className="flex flex-col gap-3 lg:flex-row lg:items-stretch lg:gap-2">
      {STEPS.map((step, index) => (
        <Fragment key={step.label}>
          <li className="flex flex-1 flex-col gap-2 rounded-xl border border-border/60 bg-card/40 p-4">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs tabular-nums text-muted-foreground">
                {String(index + 1).padStart(2, "0")}
              </span>
              <step.Icon className="size-4 text-muted-foreground" aria-hidden />
            </div>
            <span className="font-mono text-xs uppercase tracking-wider text-foreground">
              {step.label}
            </span>
            <p className="text-xs leading-relaxed text-muted-foreground">{step.desc}</p>
          </li>
          {index < STEPS.length - 1 && (
            <div className="hidden items-center justify-center lg:flex" aria-hidden>
              <ArrowRight className="size-4 text-muted-foreground/40" />
            </div>
          )}
        </Fragment>
      ))}
    </ol>
  );
}
