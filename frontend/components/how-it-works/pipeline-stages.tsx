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

interface Stage {
  label: string;
  tech: string;
  body: string;
  Icon: LucideIcon;
}

const STAGES: Stage[] = [
  {
    label: "Fetch and dedup",
    tech: "Hacker News plus 22 RSS feeds",
    Icon: Rss,
    body: "Hacker News and 22 RSS feeds are fetched concurrently and normalized into one article record, identified by canonical URL. Articles already stored, repeated within the run, or published more than 14 days ago are dropped before any model call.",
  },
  {
    label: "Classify",
    tech: "Claude Haiku 4.5, structured output",
    Icon: Filter,
    body: "Each new article gets one structured call that returns topics, a relevance score from 0 to 1, a noise flag and the named entities it covers. Articles flagged as noise stop here. Haiku is used because this call runs on every article.",
  },
  {
    label: "Embed",
    tech: "text-embedding-3-small, 768 dimensions",
    Icon: Boxes,
    body: "Each remaining article becomes one vector built from its headline, the first 8,000 characters of its body and its feed tags. The model's 1,536 dimensions are truncated to 768 to match the database column.",
  },
  {
    label: "Cluster",
    tech: "hand-written cosine, entity anchored",
    Icon: Network,
    body: "A single greedy pass compares each new article with the average vector of every open story and joins the closest one when the clustering rule matches. A story stays open for seven days from its first article. Groups that never reach two articles are dropped.",
  },
  {
    label: "Synthesize",
    tech: "Claude Sonnet 4.6, new and growing stories",
    Icon: Sparkles,
    body: "New stories, and existing stories that gained articles, get one call that writes a headline, a summary and a one-line takeaway. The model receives headlines, article text and source names, all of them for a new story and the eight newest for a growing one, and never vectors or clustering state.",
  },
  {
    label: "Rank by momentum",
    tech: "recency weighted decay",
    Icon: Gauge,
    body: "Each article adds 0.5 to the power of its age in hours divided by 72, with age measured from publication. Scores are summed, so a story with more recent coverage ranks higher, and a card shows 100 × score ÷ (score + 5). A story with no article newer than 168 hours becomes stale and leaves the feed.",
  },
];

export function PipelineStages() {
  return (
    <div className="flex flex-col">
      {STAGES.map((stage, i) => {
        const isLast = i === STAGES.length - 1;
        return (
          <motion.div
            key={stage.label}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="grid grid-cols-[2.25rem_1fr] gap-x-4"
          >
            <div className="relative flex flex-col items-center">
              <span className="z-10 flex size-9 shrink-0 items-center justify-center rounded-full border border-border bg-card text-muted-foreground">
                <stage.Icon className="size-4" aria-hidden />
              </span>
              {!isLast && <span className="w-px flex-1 bg-border" />}
            </div>
            <div className={`flex flex-col gap-2 ${isLast ? "" : "pb-10"}`}>
              <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                <h3 className="text-base font-semibold tracking-tight">
                  {stage.label}
                </h3>
                <span className="text-[13px] text-muted-foreground">{stage.tech}</span>
              </div>
              <p className="max-w-[68ch] text-pretty leading-relaxed text-muted-foreground">
                {stage.body}
              </p>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
