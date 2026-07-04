"use client";

import {
  motion,
  useReducedMotion,
  useTime,
  useTransform,
  type MotionValue,
} from "motion/react";

import { momentumColor } from "@/lib/momentum";

// The pipeline as a self-distilling funnel: a firehose is read, the noise breaks
// off and falls away, and a handful of ranked stories remain. Real numbers count
// up; the motion is restrained (fills + counts + one clean drop), not a loop of
// flying parts. Swap the constants for live `pipeline_runs` stats when wired.
const CYCLE = 10000; // ms per loop (mostly a hold; it re-animates every ~10s)
const READ = 214;
const NOISE = 173;
const SIGNAL = READ - NOISE; // 41
const STORIES = 9;
const FEEDS = 21;
const HOT = 92;

const ROW = "grid grid-cols-[4.5rem_1fr_auto] items-center gap-3";
const LABEL = "font-mono text-[10px] uppercase tracking-wider text-muted-foreground";
const NUM = "font-mono text-sm tabular-nums";

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

function StatRow({
  progress,
  at,
  label,
  to,
  widthPct,
  color,
}: {
  progress: MotionValue<number>;
  at: number;
  label: string;
  to: number;
  widthPct: number;
  color: string;
}) {
  return (
    <Reveal progress={progress} at={at} className={ROW}>
      <span className={LABEL}>{label}</span>
      <Bar progress={progress} at={at} widthPct={widthPct} color={color} />
      <span className={`${NUM} text-foreground`}>
        <Count progress={progress} to={to} at={at} />
      </span>
    </Reveal>
  );
}

function NoiseRow({ progress }: { progress: MotionValue<number> }) {
  const opacity = useTransform(progress, [0.16, 0.2, 0.28, 0.36], [0, 1, 1, 0]);
  const y = useTransform(progress, [0.28, 0.36], [0, 18], { clamp: true });
  const scaleX = useTransform(progress, [0.18, 0.26], [0, 1], { clamp: true });
  return (
    <motion.div style={{ opacity, y }} className={ROW}>
      <span className="font-mono text-[10px] uppercase tracking-wider text-red-400/80">
        noise
      </span>
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-border/25">
        <motion.div
          className="absolute left-0 top-0 h-full origin-left rounded-full bg-red-500/70"
          style={{ width: `${(NOISE / READ) * 100}%`, scaleX }}
        />
      </div>
      <span className={`${NUM} text-red-400/80`}>−{NOISE}</span>
    </motion.div>
  );
}

function StoriesRow({ progress }: { progress: MotionValue<number> }) {
  const at = 0.42;
  return (
    <Reveal progress={progress} at={at} className={ROW}>
      <span className={LABEL}>stories</span>
      <div className="flex gap-1">
        {Array.from({ length: STORIES }).map((_, i) => (
          <span key={i} className="size-2 rounded-[3px] bg-foreground/70" />
        ))}
      </div>
      <span className={`${NUM} text-foreground`}>
        <Count progress={progress} to={STORIES} at={at} />
      </span>
    </Reveal>
  );
}

export function PipelineAnimation() {
  const reduce = useReducedMotion();
  const time = useTime();
  const progress = useTransform(time, (t) => (t % CYCLE) / CYCLE);

  if (reduce) return <FunnelStatic />;

  const hot = momentumColor(HOT);

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border/60 bg-card/40 p-5">
      <Reveal
        progress={progress}
        at={0.02}
        className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground"
      >
        <span className="size-1.5 rounded-full bg-emerald-500" />
        <span className="text-foreground tabular-nums">
          <Count progress={progress} to={FEEDS} at={0.02} />
        </span>
        feeds monitored · today&apos;s run
      </Reveal>

      <div className="flex flex-col gap-2.5">
        <StatRow
          progress={progress}
          at={0.08}
          label="read"
          to={READ}
          widthPct={100}
          color="var(--muted-foreground)"
        />
        <NoiseRow progress={progress} />
        <StatRow
          progress={progress}
          at={0.3}
          label="signal"
          to={SIGNAL}
          widthPct={(SIGNAL / READ) * 100}
          color="var(--foreground)"
        />
        <StoriesRow progress={progress} />
      </div>

      <Reveal
        progress={progress}
        at={0.54}
        className={`${ROW} border-t border-border/50 pt-3`}
      >
        <span className={LABEL}>hottest</span>
        <span className="truncate text-xs font-medium text-foreground">
          Anthropic ships Opus 4.8 · 6 outlets
        </span>
        <span
          className="font-mono text-lg font-semibold tabular-nums"
          style={{ color: hot }}
        >
          <Count progress={progress} to={HOT} at={0.54} />
        </span>
      </Reveal>
    </div>
  );
}

function FunnelStatic() {
  const hot = momentumColor(HOT);
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border/60 bg-card/40 p-5">
      <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        <span className="size-1.5 rounded-full bg-emerald-500" />
        <span className="text-foreground tabular-nums">{FEEDS}</span>
        feeds monitored · today&apos;s run
      </div>
      <div className="flex flex-col gap-2.5">
        <div className={ROW}>
          <span className={LABEL}>read</span>
          <div className="h-2 w-full rounded-full bg-muted-foreground/60" />
          <span className={`${NUM} text-foreground`}>{READ}</span>
        </div>
        <div className={`${ROW} opacity-60`}>
          <span className="font-mono text-[10px] uppercase tracking-wider text-red-400/80">
            noise
          </span>
          <div className="relative h-2 w-full overflow-hidden rounded-full bg-border/25">
            <div
              className="h-full rounded-full bg-red-500/70 line-through"
              style={{ width: `${(NOISE / READ) * 100}%` }}
            />
          </div>
          <span className={`${NUM} text-red-400/80`}>−{NOISE}</span>
        </div>
        <div className={ROW}>
          <span className={LABEL}>signal</span>
          <div className="relative h-2 w-full rounded-full bg-border/25">
            <div
              className="h-full rounded-full bg-foreground"
              style={{ width: `${(SIGNAL / READ) * 100}%` }}
            />
          </div>
          <span className={`${NUM} text-foreground`}>{SIGNAL}</span>
        </div>
        <div className={ROW}>
          <span className={LABEL}>stories</span>
          <div className="flex gap-1">
            {Array.from({ length: STORIES }).map((_, i) => (
              <span key={i} className="size-2 rounded-[3px] bg-foreground/70" />
            ))}
          </div>
          <span className={`${NUM} text-foreground`}>{STORIES}</span>
        </div>
      </div>
      <div className={`${ROW} border-t border-border/50 pt-3`}>
        <span className={LABEL}>hottest</span>
        <span className="truncate text-xs font-medium text-foreground">
          Anthropic ships Opus 4.8 · 6 outlets
        </span>
        <span
          className="font-mono text-lg font-semibold tabular-nums"
          style={{ color: hot }}
        >
          {HOT}
        </span>
      </div>
    </div>
  );
}
