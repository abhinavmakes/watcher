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
import { motion, useReducedMotion, type Variants } from "motion/react";

interface Stage {
  label: string;
  tech: string;
  body: string;
  Icon: LucideIcon;
  // Same run as the "Cost and speed" table below (12 Sep 2026) — played back stage by
  // stage instead of read off a row, not a second, possibly-drifting set of numbers.
  stat?: string;
  seconds: number;
}

const STAGES: Stage[] = [
  {
    label: "Fetch and dedup",
    tech: "Hacker News plus 22 RSS feeds",
    Icon: Rss,
    body: "Hacker News and 22 RSS feeds are fetched concurrently and normalized into one article record, identified by canonical URL. Articles already stored, repeated within the run, or published more than 14 days ago are dropped before any model call.",
    stat: "374 fetched, 120 already known",
    seconds: 29,
  },
  {
    label: "Classify",
    tech: "Claude Haiku 4.5, structured output",
    Icon: Filter,
    body: "Each new article gets one structured call that returns topics, a relevance score from 0 to 1, a noise flag and the named entities it covers. Articles flagged as noise stop here. Haiku is used because this call runs on every article.",
    stat: "247 classified",
    seconds: 1526,
  },
  {
    label: "Embed",
    tech: "text-embedding-3-small, 768 dimensions",
    Icon: Boxes,
    body: "Each remaining article becomes one vector built from its headline, the first 8,000 characters of its body and its feed tags. The model's 1,536 dimensions are truncated to 768 to match the database column.",
    seconds: 10,
  },
  {
    label: "Cluster",
    tech: "hand-written cosine, entity anchored",
    Icon: Network,
    body: "A single greedy pass compares each new article with the average vector of every open story and joins the closest one when the clustering rule matches. A story stays open for seven days from its first article. Groups that never reach two articles are dropped.",
    seconds: 2,
  },
  {
    label: "Synthesize",
    tech: "Claude Sonnet 4.6, new and growing stories",
    Icon: Sparkles,
    body: "New stories, and existing stories that gained articles, get one call that writes a headline, a summary and a one-line takeaway. The model receives headlines, article text and source names, all of them for a new story and the eight newest for a growing one, and never vectors or clustering state.",
    seconds: 232,
  },
  {
    label: "Rank by momentum",
    tech: "recency weighted decay",
    Icon: Gauge,
    body: "Each article adds 0.5 to the power of its age in hours divided by 72, with age measured from publication. Scores are summed, so a story with more recent coverage ranks higher, and a card shows 100 × score ÷ (score + 5). A story with no article newer than 168 hours becomes stale and leaves the feed.",
    seconds: 8,
  },
];

function formatDuration(totalSeconds: number): string {
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`;
}

const EASE = [0.25, 0.46, 0.45, 0.94] as const;
const STAGE_STAGGER = 0.5;

const container: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: STAGE_STAGGER, delayChildren: 0.1 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE } },
};

// Pops in rather than fading, so each stage reads as firing rather than merely arriving.
const icon: Variants = {
  hidden: { opacity: 0, scale: 0.7 },
  visible: { opacity: 1, scale: [0.7, 1.14, 1], transition: { duration: 0.5, times: [0, 0.6, 1], ease: EASE } },
};

// Lands after the icon's pop, as if this is the number the stage above just produced.
const stat: Variants = {
  hidden: { opacity: 0, y: 4 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, delay: 0.2, ease: EASE } },
};

// Draws downward into the next stage instead of sitting there pre-drawn, so the pipeline
// reads as running rather than as a static diagram that happens to fade in.
const connector: Variants = {
  hidden: { scaleY: 0 },
  visible: { scaleY: 1, transition: { duration: 0.4, delay: 0.3, ease: EASE } },
};

function statLine(s: Stage): string {
  const duration = formatDuration(s.seconds);
  return s.stat ? `${s.stat} · ${duration}` : duration;
}

function AnimatedStages() {
  return (
    <motion.div
      className="flex flex-col"
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-100px" }}
      variants={container}
    >
      {STAGES.map((s, i) => {
        const isLast = i === STAGES.length - 1;
        return (
          <motion.div key={s.label} variants={item} className="grid grid-cols-[2.25rem_1fr] gap-x-4">
            <div className="relative flex flex-col items-center">
              <motion.span
                variants={icon}
                className="z-10 flex size-9 shrink-0 items-center justify-center rounded-full border border-border bg-card text-muted-foreground"
              >
                <s.Icon className="size-4" aria-hidden />
              </motion.span>
              {!isLast && (
                <motion.span
                  variants={connector}
                  style={{ transformOrigin: "top" }}
                  className="w-px flex-1 bg-border"
                />
              )}
            </div>
            <div className={`flex flex-col gap-2 ${isLast ? "" : "pb-10"}`}>
              <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                <h3 className="text-base font-semibold tracking-tight">{s.label}</h3>
                <span className="text-[13px] text-muted-foreground">{s.tech}</span>
              </div>
              <p className="max-w-[68ch] text-pretty leading-relaxed text-muted-foreground">
                {s.body}
              </p>
              <motion.p variants={stat} className="text-[13px] tabular-nums text-muted-foreground/80">
                {statLine(s)}
              </motion.p>
            </div>
          </motion.div>
        );
      })}
    </motion.div>
  );
}

function StaticStages() {
  return (
    <div className="flex flex-col">
      {STAGES.map((s, i) => {
        const isLast = i === STAGES.length - 1;
        return (
          <div key={s.label} className="grid grid-cols-[2.25rem_1fr] gap-x-4">
            <div className="relative flex flex-col items-center">
              <span className="z-10 flex size-9 shrink-0 items-center justify-center rounded-full border border-border bg-card text-muted-foreground">
                <s.Icon className="size-4" aria-hidden />
              </span>
              {!isLast && <span className="w-px flex-1 bg-border" />}
            </div>
            <div className={`flex flex-col gap-2 ${isLast ? "" : "pb-10"}`}>
              <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                <h3 className="text-base font-semibold tracking-tight">{s.label}</h3>
                <span className="text-[13px] text-muted-foreground">{s.tech}</span>
              </div>
              <p className="max-w-[68ch] text-pretty leading-relaxed text-muted-foreground">
                {s.body}
              </p>
              <p className="text-[13px] tabular-nums text-muted-foreground/80">{statLine(s)}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function PipelineStages() {
  const reduceMotion = useReducedMotion();
  return reduceMotion ? <StaticStages /> : <AnimatedStages />;
}
