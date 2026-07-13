"use client";

import {
  motion,
  useReducedMotion,
  useTime,
  useTransform,
  type MotionValue,
} from "motion/react";

import { useClusters } from "@/hooks/use-clusters";
import { momentumColor } from "@/lib/momentum";

// The real pipeline as a self-distilling funnel, one explicit step at a time:
// fetch → classify & drop noise → cluster → rank. The fetch/noise/useful counts are
// representative (swap for live `pipeline_runs` stats); the story count and the
// hottest story are pulled live from the loaded feed — so the funnel ends on the
// actual #1 card.
const CYCLE = 12000; // ms per loop (long hold; re-animates every ~12s)
const FEEDS = 21;
const FETCHED = 214;
const NOISE = 173;
const USEFUL = FETCHED - NOISE; // 41
const STORIES_FALLBACK = 8;
const HOT_FALLBACK = 92;

const LABEL = "font-mono text-[10px] uppercase tracking-wider text-muted-foreground";
const NUM = "font-mono text-sm tabular-nums";
const CAPTION = "text-[11px] leading-tight text-muted-foreground";
const FETCH_CAPTION = "from Hacker News + 20 curated AI & tech outlets";

interface HotStory {
  value: number;
  title: string;
  outlets: number;
}

function useHottest(): { hot: HotStory; stories: number } {
  const { page } = useClusters();
  const cards = page?.cards ?? [];
  const top =
    cards.length > 0
      ? [...cards].sort((a, b) => b.momentum - a.momentum)[0]
      : null;
  return {
    hot: top
      ? {
          value: Math.round(top.momentum),
          title: `${top.title} · ${top.article_count} outlets`,
          outlets: top.article_count,
        }
      : {
          value: HOT_FALLBACK,
          title: "Anthropic ships Opus 4.8 · 6 outlets",
          outlets: 6,
        },
    stories: cards.length > 0 ? (page?.total ?? cards.length) : STORIES_FALLBACK,
  };
}

function Count({
  progress,
  to,
  at,
  dur = 0.1,
}: {
  progress: MotionValue<number>;
  to: number;
  at: number;
  dur?: number;
}) {
  const text = useTransform(progress, (p) => {
    const c = Math.max(0, Math.min(1, (p - at) / dur));
    return String(Math.round(c * to));
  });
  return <motion.span>{text}</motion.span>;
}

function Reveal({
  progress,
  at,
  className,
  children,
}: {
  progress: MotionValue<number>;
  at: number;
  className?: string;
  children: React.ReactNode;
}) {
  const opacity = useTransform(progress, [at, at + 0.05], [0, 1], { clamp: true });
  const y = useTransform(progress, [at, at + 0.05], [6, 0], { clamp: true });
  return (
    <motion.div style={{ opacity, y }} className={className}>
      {children}
    </motion.div>
  );
}

function Bar({
  progress,
  at,
  widthPct,
  color,
}: {
  progress: MotionValue<number>;
  at: number;
  widthPct: number;
  color: string;
}) {
  const scaleX = useTransform(progress, [at, at + 0.12], [0, 1], { clamp: true });
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-border/25">
      <motion.div
        className="absolute left-0 top-0 h-full origin-left rounded-full"
        style={{ width: `${widthPct}%`, backgroundColor: color, scaleX }}
      />
    </div>
  );
}

function StatStage({
  progress,
  at,
  label,
  caption,
  to,
  widthPct,
  color,
}: {
  progress: MotionValue<number>;
  at: number;
  label: string;
  caption: string;
  to: number;
  widthPct: number;
  color: string;
}) {
  return (
    <Reveal progress={progress} at={at} className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className={LABEL}>{label}</span>
        <span className={`${NUM} text-foreground`}>
          <Count progress={progress} to={to} at={at} />
        </span>
      </div>
      <p className={CAPTION}>{caption}</p>
      <Bar progress={progress} at={at} widthPct={widthPct} color={color} />
    </Reveal>
  );
}

function NoiseStage({ progress }: { progress: MotionValue<number> }) {
  const opacity = useTransform(progress, [0.16, 0.2, 0.28, 0.36], [0, 1, 1, 0]);
  const y = useTransform(progress, [0.28, 0.36], [0, 16], { clamp: true });
  const scaleX = useTransform(progress, [0.18, 0.26], [0, 1], { clamp: true });
  return (
    <motion.div style={{ opacity, y }} className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-wider text-red-400/80">
          Dropped noise
        </span>
        <span className={`${NUM} text-red-400/80`}>−{NOISE}</span>
      </div>
      <p className={CAPTION}>low-quality & off-topic, filtered out</p>
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-border/25">
        <motion.div
          className="absolute left-0 top-0 h-full origin-left rounded-full bg-red-500/70"
          style={{ width: `${(NOISE / FETCHED) * 100}%`, scaleX }}
        />
      </div>
    </motion.div>
  );
}

function StoriesStage({
  progress,
  count,
}: {
  progress: MotionValue<number>;
  count: number;
}) {
  const at = 0.4;
  const blocks = Math.min(Math.max(count, 1), 10);
  return (
    <Reveal progress={progress} at={at} className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className={LABEL}>Clustered into stories</span>
        <span className={`${NUM} text-foreground`}>
          <Count progress={progress} to={count} at={at} />
        </span>
      </div>
      <p className={CAPTION}>same event across outlets, grouped into one story</p>
      <div className="flex gap-1.5">
        {Array.from({ length: blocks }).map((_, i) => (
          <span key={i} className="h-2 flex-1 rounded-[3px] bg-foreground/70" />
        ))}
      </div>
    </Reveal>
  );
}

export function PipelineAnimation() {
  const reduce = useReducedMotion();
  const time = useTime();
  const progress = useTransform(time, (t) => (t % CYCLE) / CYCLE);
  const { hot, stories } = useHottest();

  if (reduce) return <FunnelStatic hot={hot} stories={stories} />;

  const hotColor = momentumColor(hot.value);

  return (
    <div className="flex flex-col gap-3.5 rounded-xl border border-border/60 bg-card/40 p-5">
      <Reveal
        progress={progress}
        at={0.02}
        className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground"
      >
        <span className="size-1.5 rounded-full bg-emerald-500" />
        <span className="tabular-nums text-foreground">
          <Count progress={progress} to={FEEDS} at={0.02} />
        </span>
        feeds monitored · today&apos;s run
      </Reveal>

      <StatStage
        progress={progress}
        at={0.08}
        label="Fetched"
        caption={FETCH_CAPTION}
        to={FETCHED}
        widthPct={100}
        color="var(--muted-foreground)"
      />
      <NoiseStage progress={progress} />
      <StatStage
        progress={progress}
        at={0.3}
        label="Useful"
        caption="classified & scored for relevance (Haiku)"
        to={USEFUL}
        widthPct={(USEFUL / FETCHED) * 100}
        color="var(--foreground)"
      />
      <StoriesStage progress={progress} count={stories} />

      <Reveal
        progress={progress}
        at={0.5}
        className="flex flex-col gap-1 border-t border-border/50 pt-3"
      >
        <div className="flex items-baseline justify-between gap-2">
          <span className={LABEL}>Hottest story</span>
          <span
            className="font-mono text-lg font-semibold tabular-nums"
            style={{ color: hotColor }}
          >
            <Count progress={progress} to={hot.value} at={0.5} />
          </span>
        </div>
        <p className={CAPTION}>ranked by how many outlets covered it right now</p>
        <p className="truncate text-xs font-medium text-foreground">{hot.title}</p>
      </Reveal>
    </div>
  );
}

function FunnelStatic({ hot, stories }: { hot: HotStory; stories: number }) {
  const hotColor = momentumColor(hot.value);
  const row = "flex flex-col gap-1";
  const blocks = Math.min(Math.max(stories, 1), 10);
  return (
    <div className="flex flex-col gap-3.5 rounded-xl border border-border/60 bg-card/40 p-5">
      <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        <span className="size-1.5 rounded-full bg-emerald-500" />
        <span className="tabular-nums text-foreground">{FEEDS}</span>
        feeds monitored · today&apos;s run
      </div>

      <div className={row}>
        <div className="flex items-baseline justify-between">
          <span className={LABEL}>Fetched</span>
          <span className={`${NUM} text-foreground`}>{FETCHED}</span>
        </div>
        <p className={CAPTION}>{FETCH_CAPTION}</p>
        <div className="h-2 w-full rounded-full bg-muted-foreground/60" />
      </div>

      <div className={`${row} opacity-60`}>
        <div className="flex items-baseline justify-between">
          <span className="font-mono text-[10px] uppercase tracking-wider text-red-400/80">
            Dropped noise
          </span>
          <span className={`${NUM} text-red-400/80`}>−{NOISE}</span>
        </div>
        <p className={CAPTION}>low-quality & off-topic, filtered out</p>
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-border/25">
          <div
            className="h-full rounded-full bg-red-500/70"
            style={{ width: `${(NOISE / FETCHED) * 100}%` }}
          />
        </div>
      </div>

      <div className={row}>
        <div className="flex items-baseline justify-between">
          <span className={LABEL}>Useful</span>
          <span className={`${NUM} text-foreground`}>{USEFUL}</span>
        </div>
        <p className={CAPTION}>classified & scored for relevance (Haiku)</p>
        <div className="relative h-2 w-full rounded-full bg-border/25">
          <div
            className="h-full rounded-full bg-foreground"
            style={{ width: `${(USEFUL / FETCHED) * 100}%` }}
          />
        </div>
      </div>

      <div className={row}>
        <div className="flex items-baseline justify-between">
          <span className={LABEL}>Clustered into stories</span>
          <span className={`${NUM} text-foreground`}>{stories}</span>
        </div>
        <p className={CAPTION}>same event across outlets, grouped into one story</p>
        <div className="flex gap-1.5">
          {Array.from({ length: blocks }).map((_, i) => (
            <span key={i} className="h-2 flex-1 rounded-[3px] bg-foreground/70" />
          ))}
        </div>
      </div>

      <div className={`${row} border-t border-border/50 pt-3`}>
        <div className="flex items-baseline justify-between">
          <span className={LABEL}>Hottest story</span>
          <span
            className="font-mono text-lg font-semibold tabular-nums"
            style={{ color: hotColor }}
          >
            {hot.value}
          </span>
        </div>
        <p className={CAPTION}>ranked by how many outlets covered it right now</p>
        <p className="truncate text-xs font-medium text-foreground">{hot.title}</p>
      </div>
    </div>
  );
}
