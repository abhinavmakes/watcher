"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, useInView, useReducedMotion, type Variants } from "motion/react";

import { useCluster } from "@/hooks/use-cluster";
import { useClusters } from "@/hooks/use-clusters";
import { useLatestRun } from "@/hooks/use-latest-run";
import { hostname } from "@/lib/links";
import { momentumColor } from "@/lib/momentum";
import type { ClusterDetail } from "@/lib/types";

// The one claim the product makes, shown with live data: a week of articles arrives, a few of
// them turn out to be the same event, and the feed carries that event once. Everything on
// screen is real, so the section hides itself rather than invent a demo when no current story
// spans enough outlets.
const CANDIDATES = 4;
const MIN_OUTLETS = 3;
const MAX_LINES = 4;

const CHIP_HEIGHT = 52;
const CHIP_GAP = 10;
const CHIP_ROWS = 3;
const STAGE_HEIGHT = CHIP_ROWS * (CHIP_HEIGHT + CHIP_GAP) - CHIP_GAP;
const CARD_MAX_WIDTH = 560;

// A Google News link is a redirect to a publisher, and the same article usually also arrives
// from that publisher directly, so counting it as an outlet would overstate the coverage.
const REDIRECTORS = new Set(["news.google.com"]);

const PHASES = ["arrive", "narrow", "fold", "settled"] as const;
type Phase = (typeof PHASES)[number];
const PHASE_MS: Record<Phase, number> = { arrive: 2000, narrow: 1200, fold: 950, settled: 3200 };

interface SourceLine {
  outlet: string;
  title: string;
}

// Articles arrive newest first, so the first title seen for an outlet is its latest one.
function sourceLines(detail: ClusterDetail): SourceLine[] {
  const latestPerOutlet = new Map<string, string>();
  for (const article of detail.articles) {
    const outlet = hostname(article.url);
    if (!outlet || REDIRECTORS.has(outlet)) continue;
    if (!latestPerOutlet.has(outlet)) latestPerOutlet.set(outlet, article.title);
  }
  return [...latestPerOutlet].map(([outlet, title]) => ({ outlet, title }));
}

// Headlines for the chips that are not part of the story. They come from the other stories
// already fetched for this section, so the grid is a real sample of the week rather than filler.
// Taken round robin across outlets, because one single-publisher digest holds seventeen of them
// and reading them off in order fills the whole grid with the same name.
function otherHeadlines(details: (ClusterDetail | undefined)[], story: ClusterDetail): SourceLine[] {
  const seen = new Set<string>();
  const byOutlet = new Map<string, SourceLine[]>();
  for (const detail of details) {
    if (!detail || detail.id === story.id) continue;
    for (const article of detail.articles) {
      const outlet = hostname(article.url);
      if (!outlet || REDIRECTORS.has(outlet) || seen.has(article.title)) continue;
      seen.add(article.title);
      const queue = byOutlet.get(outlet) ?? [];
      queue.push({ outlet, title: article.title });
      byOutlet.set(outlet, queue);
    }
  }

  const queues = [...byOutlet.values()];
  const lines: SourceLine[] = [];
  for (let round = 0, added = true; added; round += 1) {
    added = false;
    for (const queue of queues) {
      const line = queue[round];
      if (line === undefined) continue;
      lines.push(line);
      added = true;
    }
  }
  return lines;
}

interface Chip extends SourceLine {
  key: string;
  isStory: boolean;
  left: number;
  top: number;
  width: number;
  // Offset from this chip's own slot to the middle of the stage, where the card lands.
  dx: number;
  dy: number;
  order: number;
}

function columnsFor(width: number): number {
  if (width < 520) return 2;
  if (width < 900) return 3;
  return 4;
}

// Spread the story's chips across the grid so the gather reads as convergence rather than a
// column sliding sideways. Slots are derived, not random, so the layout is stable between runs.
function storySlots(count: number, total: number, columns: number): number[] {
  const taken = new Set<number>();
  for (let index = 0; index < count; index += 1) {
    const base = Math.floor((index * total) / count) + Math.floor(total / (2 * count));
    const row = Math.floor(base / columns);
    const shifted = (base % columns) + (index % 2 === 0 ? -1 : 1);
    const column = Math.min(columns - 1, Math.max(0, shifted));
    let slot = row * columns + column;
    while (taken.has(slot)) slot = (slot + 1) % total;
    taken.add(slot);
  }
  return [...taken];
}

function buildChips(width: number, story: SourceLine[], others: SourceLine[]): Chip[] {
  const columns = columnsFor(width);
  const total = columns * CHIP_ROWS;
  const chipWidth = (width - CHIP_GAP * (columns - 1)) / columns;
  const slots = storySlots(story.length, total, columns);

  const chips: Chip[] = [];
  let storyIndex = 0;
  let otherIndex = 0;

  for (let slot = 0; slot < total; slot += 1) {
    const isStory = slots.includes(slot);
    // A slot with no real headline behind it stays empty. Repeating one to fill the grid
    // would be the same invented padding the old animation was removed for.
    const line = isStory ? story[storyIndex++] : others[otherIndex++];
    if (!line) continue;
    const left = (slot % columns) * (chipWidth + CHIP_GAP);
    const top = Math.floor(slot / columns) * (CHIP_HEIGHT + CHIP_GAP);
    chips.push({
      ...line,
      key: `${slot}-${line.outlet}`,
      isStory,
      left,
      top,
      width: chipWidth,
      dx: width / 2 - (left + chipWidth / 2),
      dy: STAGE_HEIGHT / 2 - (top + CHIP_HEIGHT / 2),
      order: slot,
    });
  }
  return chips;
}

// One easing curve for every phase. Mixing easeOut/easeInOut/a material curve per phase is
// what made the sequence read as stitched clips instead of one continuous motion.
const EASE = [0.25, 0.46, 0.45, 0.94] as const;

const chipVariants: Variants = {
  arrive: ({ order }: Chip) => ({
    opacity: 1,
    x: 0,
    y: 0,
    scale: 1,
    filter: "blur(0px)",
    transition: { duration: 0.4, delay: order * 0.045, ease: EASE },
  }),
  narrow: ({ isStory, order }: Chip) => ({
    opacity: isStory ? 1 : 0,
    x: isStory ? 0 : order % 2 === 0 ? -6 : 6,
    y: isStory ? 0 : 6,
    scale: isStory ? 1.03 : 0.9,
    filter: "blur(0px)",
    // The rest drift and dissolve in the order they arrived rather than all at once, so the
    // three that stay look picked out rather than left over.
    transition: { duration: 0.5, delay: isStory ? 0.1 : order * 0.025, ease: EASE },
  }),
  fold: ({ isStory, dx, dy }: Chip) => ({
    opacity: 0,
    x: isStory ? dx : 0,
    y: isStory ? dy : 0,
    scale: isStory ? 0.92 : 0.95,
    // Story chips blur as they converge, so the sharpening card reads as the same motion
    // coming into focus rather than an unrelated element appearing after they vanish.
    filter: isStory ? "blur(6px)" : "blur(0px)",
    transition: {
      duration: 0.6,
      ease: EASE,
      opacity: { duration: 0.3, delay: 0.3 },
    },
  }),
  settled: { opacity: 0, transition: { duration: 0.2 } },
};

// The card starts fading in partway through "fold" — while the story chips are still
// converging and blurring out — instead of waiting for the "settled" phase to begin. That
// overlap is what turns "chips vanish, then a card appears" into a single cross-fade.
const cardVariants: Variants = {
  arrive: { opacity: 0, scale: 0.96, filter: "blur(8px)", transition: { duration: 0.3, ease: EASE } },
  narrow: { opacity: 0, scale: 0.96, filter: "blur(8px)", transition: { duration: 0.3, ease: EASE } },
  fold: {
    opacity: 1,
    scale: 1,
    filter: "blur(0px)",
    transition: { duration: 0.5, delay: 0.35, ease: EASE },
  },
  settled: { opacity: 1, scale: 1, filter: "blur(0px)", transition: { duration: 0.3, ease: EASE } },
};

function ChipBody({ line }: { line: SourceLine }) {
  return (
    <div
      className="card-surface flex flex-col justify-center gap-0.5 overflow-hidden rounded-md px-3"
      style={{ height: CHIP_HEIGHT }}
    >
      <span className="truncate text-[11px] text-muted-foreground">
        {line.outlet}
      </span>
      <span className="truncate text-[13px] leading-snug text-foreground">{line.title}</span>
    </div>
  );
}

// The card sits on the edges of the articles it folded together, so the stack survives the
// animation and the idea still reads in a screenshot.
function StoryCard({ detail, buried }: { detail: ClusterDetail; buried: number }) {
  return (
    <div className="relative">
      {Array.from({ length: buried }, (_, index) => (
        <div
          key={index}
          aria-hidden
          className="card-surface absolute inset-0 rounded-lg"
          style={{ transform: `translateY(${(index + 1) * 5}px) scale(${1 - (index + 1) * 0.018})` }}
        />
      ))}
      <Link
        href={`/cluster/${detail.id}`}
        className="card-surface relative flex flex-col gap-2 rounded-lg p-4 transition-shadow duration-200 hover:card-surface-hover"
      >
        <div className="flex items-start justify-between gap-4">
          <span className="line-clamp-2 text-pretty text-[15px] font-semibold leading-snug tracking-tight text-foreground">
            {detail.title}
          </span>
          <span
            className="shrink-0 font-mono text-3xl font-medium leading-none tabular-nums"
            style={{ color: momentumColor(detail.momentum) }}
          >
            {Math.round(detail.momentum)}
          </span>
        </div>
        <span className="text-[13px] text-muted-foreground">
          {detail.article_count} {detail.article_count === 1 ? "source" : "sources"}
        </span>
      </Link>
    </div>
  );
}

interface StageProps {
  detail: ClusterDetail;
  story: SourceLine[];
  others: SourceLine[];
  fetched: number | undefined;
}

function captions({ detail, story, fetched }: Omit<StageProps, "others">): Record<Phase, string> {
  const arrived = fetched
    ? `${fetched} articles arrived this week`
    : "A week of articles arrives";
  return {
    arrive: arrived,
    narrow: `${story.length} of them are the same event`,
    fold: "Watcher groups them into one story",
    settled: `One card, ${detail.article_count} sources, one click away`,
  };
}

function FoldStage({ detail, story, others, fetched }: StageProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const inView = useInView(stageRef, { margin: "-64px" });
  const [width, setWidth] = useState(0);
  const [phase, setPhase] = useState<Phase>("arrive");

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(stage);
    return () => observer.disconnect();
  }, []);

  // The loop runs forever but only while the section is on screen, so a page left open in a
  // background tab is not animating chips nobody is looking at.
  useEffect(() => {
    if (!inView || width === 0) return;
    const timer = setTimeout(() => {
      setPhase((current) => PHASES[(PHASES.indexOf(current) + 1) % PHASES.length]);
    }, PHASE_MS[phase]);
    return () => clearTimeout(timer);
  }, [inView, width, phase]);

  const chips = width > 0 ? buildChips(width, story, others) : [];
  const labels = captions({ detail, story, fetched });
  const cardWidth = Math.min(width || CARD_MAX_WIDTH, CARD_MAX_WIDTH);

  return (
    <div className="flex flex-col gap-4">
      <div aria-hidden className="relative h-5">
        {PHASES.map((name) => (
          <motion.p
            key={name}
            initial={false}
            animate={{ opacity: phase === name ? 1 : 0, y: phase === name ? 0 : 3 }}
            transition={{ duration: 0.35, ease: EASE }}
            className="absolute inset-x-0 top-0 text-[13px] leading-5 text-muted-foreground tabular-nums"
          >
            {labels[name]}
          </motion.p>
        ))}
      </div>

      <div ref={stageRef} className="relative w-full" style={{ height: STAGE_HEIGHT }}>
        <div aria-hidden className="absolute inset-0">
          {chips.map((chip) => (
            <motion.div
              key={chip.key}
              custom={chip}
              variants={chipVariants}
              initial="settled"
              animate={phase}
              className="absolute"
              style={{ left: chip.left, top: chip.top, width: chip.width }}
            >
              <ChipBody line={chip} />
            </motion.div>
          ))}
        </div>

        <div className="absolute inset-0 flex items-center justify-center">
          <motion.div
            variants={cardVariants}
            initial="arrive"
            animate={phase}
            className="w-full"
            style={{ maxWidth: cardWidth }}
          >
            <StoryCard detail={detail} buried={Math.min(story.length - 1, 3)} />
          </motion.div>
        </div>
      </div>

      <p className="sr-only">
        {labels.arrive}. {labels.narrow}. {labels.settled}.
      </p>
    </div>
  );
}

function StaticFold({ detail, story, others, fetched }: StageProps) {
  const sample = [...story, ...others].slice(0, 6);
  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13px] text-muted-foreground">
        {fetched ? `${fetched} articles arrived this week.` : "A week of articles arrives."}{" "}
        {story.length} of them are the same event.
      </p>
      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {sample.map((line, index) => (
          <div key={`${line.outlet}-${index}`} style={{ opacity: index < story.length ? 1 : 0.45 }}>
            <ChipBody line={line} />
          </div>
        ))}
      </div>
      <div className="w-full" style={{ maxWidth: CARD_MAX_WIDTH }}>
        <StoryCard detail={detail} buried={Math.min(story.length - 1, 3)} />
      </div>
      <p className="text-[13px] text-muted-foreground">
        One card, {detail.article_count} sources, one click away.
      </p>
    </div>
  );
}

export function StoryFold() {
  const { page } = useClusters();
  const { run } = useLatestRun();

  const candidates = (page?.cards ?? []).slice(0, CANDIDATES);
  const first = useCluster(candidates[0]?.id ?? "");
  const second = useCluster(candidates[1]?.id ?? "");
  const third = useCluster(candidates[2]?.id ?? "");
  const fourth = useCluster(candidates[3]?.id ?? "");
  const reduceMotion = useReducedMotion();

  const details = [first.detail, second.detail, third.detail, fourth.detail];

  // Walk the feed in its own order and take the first story that genuinely spans outlets.
  // Picking the widest story instead would favour the large entity-anchored clusters, where
  // the members share a company name rather than an event.
  const chosen = details
    .filter((detail) => detail !== undefined)
    .map((detail) => ({ detail, lines: sourceLines(detail) }))
    .find((candidate) => candidate.lines.length >= MIN_OUTLETS);

  if (chosen === undefined) return null;

  const props: StageProps = {
    detail: chosen.detail,
    story: chosen.lines.slice(0, MAX_LINES),
    others: otherHeadlines(details, chosen.detail),
    fetched: run?.articles_fetched,
  };

  return reduceMotion ? <StaticFold {...props} /> : <FoldStage {...props} />;
}
