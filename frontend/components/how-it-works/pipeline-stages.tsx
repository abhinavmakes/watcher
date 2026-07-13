"use client";

import {
  Boxes,
  Filter,
  Gauge,
  Network,
  Rss,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { motion } from "motion/react";

import { momentumColor } from "@/lib/momentum";

interface Stage {
  label: string;
  tech: string;
  body: string;
  Icon: LucideIcon;
}

// First-person, honest — draft in the builder's voice; rewrite to taste.
const STAGES: Stage[] = [
  {
    label: "Fetch & dedup",
    tech: "Hacker News · curated RSS · asyncio",
    Icon: Rss,
    body: "I pull from Hacker News and a couple dozen curated RSS feeds concurrently, then dedupe on a canonical URL so the same story syndicated across outlets doesn't get counted twice. The part I actually care about happens next: before anything touches an LLM, I filter the batch against what's already in the database and only classify articles I haven't seen. Re-classifying the whole pool every run was the single biggest recurring cost — this one check makes each run 4–10× cheaper after the cold start. The lesson I keep coming back to is that the cheapest LLM optimization is not sending the tokens at all.",
  },
  {
    label: "Classify",
    tech: "Claude Haiku · structured output",
    Icon: Filter,
    body: "Every new article goes through Claude Haiku with a structured output — domain, a 0–1 relevance score, a noise flag, and the key entities. Haiku is a deliberate choice: this is the highest-volume stage, so the cheap model belongs here, and I save the expensive one for synthesis where the output is actually read by a person. I started on Gemini Flash-Lite and moved off it after it hit a hard requests-per-day wall mid-run — prepaid Claude credits give me a spend ceiling I control instead of a quota that silently kills the pipeline.",
  },
  {
    label: "Embed",
    tech: "text-embedding-3-small · 768d",
    Icon: Boxes,
    body: "The articles that survive the noise filter get embedded with OpenAI's text-embedding-3-small at 768 dimensions. I don't embed the raw article — I format an entity-anchored input first, so the vector leans on who and what the story is about rather than incidental wording. Noise never reaches this stage, which keeps the vector space clean and the embedding bill down.",
  },
  {
    label: "Cluster",
    tech: "pgvector · cosine · entity-anchored",
    Icon: Network,
    body: "This is the core of the whole thing: grouping every outlet's take on the same event into one story. I use cosine similarity over the embeddings with two thresholds — 0.85 to join an existing cluster, 0.83 to start a new one — anchored on shared entities so two unrelated stories that happen to sound alike don't get merged. Tuning these is where I spent real time: too loose and unrelated stories collapse together, too tight and one event fragments into five clusters.",
  },
  {
    label: "Synthesize",
    tech: "Claude Sonnet · gated to 2+ articles",
    Icon: Sparkles,
    body: "For each new cluster with real coverage, Claude Sonnet writes the factual summary and the “so what.” I gate it — a cluster needs at least two articles — and I only synthesize clusters that are new this run. The input to the model is a purpose-built object, not my internal cluster: I strip out the embeddings and clustering machinery, because handing that to the model is just noise tokens that make the output worse. This is the one place I pay for the stronger model, because it writes the one line a person actually reads.",
  },
  {
    label: "Score momentum",
    tech: "recency-weighted decay sum",
    Icon: Gauge,
    body: "Momentum is how I rank. Each article in a cluster contributes a weight that halves every 24 hours, and I sum those weights instead of averaging them — a story everyone is piling onto right now should outrank a quiet one, and averaging would erase that. I recompute every active cluster on every run, not just the ones that got new articles, because a story going cold is a function of elapsed time, not of an ingestion event. The half-life (24h) sits below the stale cutoff (48h) on purpose, so the score and the “is this stale” flag never contradict each other.",
  },
];

export function PipelineStages() {
  return (
    <div className="flex flex-col">
      {STAGES.map((stage, i) => {
        const heat = momentumColor((i / (STAGES.length - 1)) * 100);
        const nextHeat = momentumColor(((i + 1) / (STAGES.length - 1)) * 100);
        const isLast = i === STAGES.length - 1;
        return (
          <motion.div
            key={stage.label}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="grid grid-cols-[2.75rem_1fr] gap-x-4"
          >
            <div className="relative flex flex-col items-center">
              <span
                className="z-10 flex size-11 shrink-0 items-center justify-center rounded-full border-2 bg-background"
                style={{
                  borderColor: heat,
                  color: heat,
                  boxShadow: `0 0 14px -3px ${heat}`,
                }}
              >
                <stage.Icon className="size-[18px]" aria-hidden />
              </span>
              {!isLast && (
                <span
                  className="w-0.5 flex-1 rounded-full"
                  style={{ background: `linear-gradient(to bottom, ${heat}, ${nextHeat})` }}
                />
              )}
            </div>
            <div className={`flex flex-col gap-2 ${isLast ? "" : "pb-8"}`}>
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span
                  className="font-mono text-xs font-semibold tabular-nums"
                  style={{ color: heat }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h2 className="text-lg font-semibold tracking-tight">{stage.label}</h2>
                <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                  {stage.tech}
                </span>
              </div>
              <p className="max-w-2xl text-pretty leading-relaxed text-muted-foreground">
                {stage.body}
              </p>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
