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
  body: string[];
  Icon: LucideIcon;
}

// Each stage gets the mechanism first and then the decision behind it, because the
// mechanism is the boring half and the decision is the half worth reading.
const STAGES: Stage[] = [
  {
    label: "Fetch and dedup",
    tech: "Hacker News plus 22 RSS feeds",
    Icon: Rss,
    body: [
      "Both sources are pulled at the same time and flattened into one record shape, which matters more than it sounds. Hacker News gives me a story object with a score and a comment count and usually no body text at all. An RSS entry gives me a body and no engagement signal. Everything downstream reads one normalized article, so neither source leaks its shape into the rest of the system.",
      "Identity is the canonical URL, stripped of tracking parameters, and deduplication happens in three places: a set within the run, a lookup against what is already stored, and a conflict rule on insert. The middle one is the expensive one to get right and the cheapest thing in the system. On the most recent run it skipped 120 of 374 articles before a single model call was made.",
    ],
  },
  {
    label: "Classify",
    tech: "Claude Haiku, structured output",
    Icon: Filter,
    body: [
      "Every surviving article is read by Claude Haiku, which returns a topic, a relevance score from 0 to 1, a noise flag, and the named entities the story is about. Those entities are free in the sense that the model was going to read the article anyway, and they turn out to carry the clustering stage later on.",
      "Model choice here is tiered by volume against stakes rather than chosen once for the whole system. This stage runs on everything, so it takes the cheap model. I began on Gemini Flash-Lite and moved off it after it hit a hard requests-per-day ceiling in the middle of a run and simply stopped. Prepaid credits give me a spending limit I control. A daily quota is a limit that decides for me, usually at the worst possible moment.",
    ],
  },
  {
    label: "Embed",
    tech: "text-embedding-3-small, 768 dimensions",
    Icon: Boxes,
    body: [
      "Whatever clears the noise flag becomes a vector. 768 dimensions rather than the full 1536 because the model supports truncation and the database column is sized to match, which halves the index size for a quality difference I could not detect at this corpus size. I build the input by hand: headline, then article body up to a character budget, then the tags the feed supplies.",
      "That character budget is the part I got wrong. It was set to 2,000 back when every article was a short blurb, and nothing made me revisit it when the feeds moved to long engineering posts. The result was that a 20,000 character article was represented by its introduction, which on a corporate engineering blog is mostly boilerplate that every post on that blog shares. The whole stage takes 10 seconds, which is the real lesson: the cheap stage was never worth optimizing and was always worth checking.",
    ],
  },
  {
    label: "Cluster",
    tech: "hand-rolled cosine, entity anchored",
    Icon: Network,
    body: [
      "A greedy single pass. Each new article is compared against the running average vector of every active story, and joins the closest one if the rule below passes. Stories that never gain a second member are discarded rather than stored, which is why the feed shows stories rather than articles.",
      "I wrote the similarity by hand instead of importing a clustering library. That was deliberate and I would defend it: the merge rule is the single most opinionated thing in this project, and a library would have imposed its own algorithm while hiding the decision I most wanted to keep readable. The performance argument does not apply either. The entire clustering stage takes under two seconds.",
    ],
  },
  {
    label: "Synthesize",
    tech: "Claude Sonnet, new stories only",
    Icon: Sparkles,
    body: [
      "Each newly formed story goes to Claude Sonnet, which writes the summary and the single line about why it matters. This is the only place the expensive model appears, and it is justified by being the only text a human actually reads. Everything else in the pipeline produces labels and numbers for other code to consume.",
      "The model receives a purpose-built object containing headlines, article text and source names. It does not receive my internal cluster, which carries vectors, centroids and threshold state. That separation is not tidiness. Prompt content is a contract, and handing a model a pile of embedding machinery is several hundred tokens of noise that measurably degrades the writing.",
    ],
  },
  {
    label: "Rank by momentum",
    tech: "recency weighted decay",
    Icon: Gauge,
    body: [
      "The number on every card. Each source in a story contributes a weight that halves every three days, counted from when the article was published rather than when the pipeline found it, and those weights are summed rather than averaged. Summing is the whole point: ten outlets covering something this week should outrank three, and averaging would collapse both to roughly the same value.",
      "Every active story is rescored on every run, including ones that received nothing new. Going cold is a function of time passing, not of anything arriving, so a pass that only visits stories touched this run would never notice a story dying. The half-life sits deliberately below the staleness cutoff, so by the time a story is marked stale its newest member is already contributing almost nothing and the two signals agree instead of contradicting each other.",
    ],
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
              {stage.body.map((paragraph) => (
                <p
                  key={paragraph.slice(0, 24)}
                  className="max-w-[68ch] text-pretty leading-relaxed text-muted-foreground"
                >
                  {paragraph}
                </p>
              ))}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
