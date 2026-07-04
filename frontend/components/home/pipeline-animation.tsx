"use client";

import { ArrowRight } from "lucide-react";
import { motion, useReducedMotion, useTime, useTransform } from "motion/react";

import { momentumColor } from "@/lib/momentum";

// A looping depiction of the real pipeline: raw headlines stream in from many
// outlets, noise gets struck out, the rest cluster into one story, and a ranked
// Signal card emerges. Timings/positions are tuned by eye — tweak DURATION/TIMES
// and the keyframe arrays to re-time it.
const DURATION = 8; // seconds per loop
const TIMES = [0, 0.12, 0.34, 0.52, 0.7, 0.86, 1];

interface ChipData {
  source: string;
  headline: string;
  top: string;
  noise?: boolean;
}

// 4 outlets covering the same story (they cluster) + 2 junk items (dropped).
const CHIPS: ChipData[] = [
  { source: "TechCrunch", headline: "Anthropic launches Claude Opus 4.8", top: "4%" },
  { source: "Crypto Daily", headline: "Bitcoin dips below $60k", top: "21%", noise: true },
  { source: "The Verge", headline: "Opus 4.8 pushes context to 1M", top: "38%" },
  { source: "Hacker News", headline: "Claude Opus 4.8 (1M context)", top: "55%" },
  { source: "RetroBlog", headline: "10 gadgets from 2005 we miss", top: "72%", noise: true },
  { source: "Ars Technica", headline: "Anthropic's new Opus model", top: "84%" },
];

const STAGES = ["Read 21 feeds", "Drop the noise", "Cluster the story", "Rank by heat"];
const STAGE_ACTIVE_AT = [1, 2, 3, 4]; // index into TIMES where each stage lights up

function ChipInner({ chip }: { chip: ChipData }) {
  return (
    <div className={chip.noise ? "opacity-70" : ""}>
      <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
        {chip.source}
      </div>
      <div className="truncate text-[11px] text-foreground/80">{chip.headline}</div>
    </div>
  );
}

function Chip({ chip }: { chip: ChipData }) {
  const base =
    "absolute w-[46%] max-w-56 rounded-md border border-border/70 bg-card px-2.5 py-1.5 shadow-sm";
  const transition = {
    duration: DURATION,
    times: TIMES,
    repeat: Infinity,
    ease: "easeInOut",
  } as const;

  if (chip.noise) {
    return (
      <motion.div
        className={base}
        style={{ left: "4%", top: chip.top }}
        initial={{ opacity: 0 }}
        animate={{
          opacity: [0, 1, 1, 0, 0, 0, 0],
          top: [chip.top, chip.top, chip.top, "118%", "118%", "118%", "118%"],
        }}
        transition={transition}
      >
        <ChipInner chip={chip} />
        <motion.span
          aria-hidden
          className="absolute inset-x-2 top-1/2 h-px origin-left bg-red-500"
          initial={{ scaleX: 0, opacity: 0 }}
          animate={{
            scaleX: [0, 0, 1, 1, 1, 1, 1],
            opacity: [0, 0, 1, 1, 0, 0, 0],
          }}
          transition={transition}
        />
      </motion.div>
    );
  }

  return (
    <motion.div
      className={base}
      style={{ left: "4%", top: chip.top }}
      initial={{ opacity: 0 }}
      animate={{
        opacity: [0, 1, 1, 1, 0, 0, 0],
        left: ["4%", "4%", "4%", "30%", "48%", "48%", "48%"],
        top: [chip.top, chip.top, chip.top, "40%", "40%", "40%", "40%"],
        scale: [0.96, 1, 1, 1, 0.88, 0.85, 0.85],
      }}
      transition={transition}
    >
      <ChipInner chip={chip} />
    </motion.div>
  );
}

function CountUp({ to }: { to: number }) {
  const time = useTime();
  const value = useTransform(time, (t) => {
    const p = (t % (DURATION * 1000)) / (DURATION * 1000);
    const c = Math.max(0, Math.min(1, (p - 0.6) / 0.12));
    return String(Math.round(c * to));
  });
  return <motion.span>{value}</motion.span>;
}

function SignalCard() {
  return (
    <motion.div
      className="absolute flex w-[44%] max-w-64 flex-col gap-1.5 rounded-lg border bg-card p-3 shadow-lg"
      style={{ left: "52%", top: "22%", borderColor: momentumColor(92, 0.5) }}
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{
        opacity: [0, 0, 0, 0, 1, 1, 0],
        scale: [0.92, 0.92, 0.92, 0.92, 1, 1, 0.98],
      }}
      transition={{ duration: DURATION, times: TIMES, repeat: Infinity, ease: "easeInOut" }}
    >
      <div className="flex items-start justify-between">
        <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
          Signal
        </span>
        <span
          className="font-mono text-3xl font-semibold leading-none tabular-nums"
          style={{ color: momentumColor(92) }}
        >
          <CountUp to={92} />
        </span>
      </div>
      <div className="text-xs font-medium leading-snug text-foreground">
        Anthropic ships Claude Opus 4.8
      </div>
      <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
        4 outlets · LLMs
      </div>
    </motion.div>
  );
}

function StageLabels() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-wider">
      {STAGES.map((label, i) => {
        const opacity = TIMES.map((_, t) => (t === STAGE_ACTIVE_AT[i] ? 1 : 0.4));
        const dotOpacity = TIMES.map((_, t) => (t === STAGE_ACTIVE_AT[i] ? 1 : 0.25));
        return (
          <motion.span
            key={label}
            className="inline-flex items-center gap-1.5 text-muted-foreground"
            animate={{ opacity }}
            transition={{ duration: DURATION, times: TIMES, repeat: Infinity }}
          >
            <motion.span
              className="size-1 rounded-full bg-emerald-500"
              animate={{ opacity: dotOpacity }}
              transition={{ duration: DURATION, times: TIMES, repeat: Infinity }}
            />
            {label}
          </motion.span>
        );
      })}
    </div>
  );
}

function PipelineStatic() {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-64 w-full items-center gap-4 rounded-xl border border-border/60 bg-card/40 p-4 sm:h-72">
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          {CHIPS.slice(0, 4).map((chip) => (
            <div
              key={chip.source}
              className={`rounded-md border border-border/70 bg-card px-2.5 py-1.5 ${
                chip.noise ? "opacity-50 line-through" : ""
              }`}
            >
              <ChipInner chip={chip} />
            </div>
          ))}
        </div>
        <ArrowRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <div
          className="w-40 shrink-0 rounded-lg border bg-card p-3"
          style={{ borderColor: momentumColor(92, 0.5) }}
        >
          <div className="flex items-start justify-between">
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
              Signal
            </span>
            <span
              className="font-mono text-3xl font-semibold leading-none"
              style={{ color: momentumColor(92) }}
            >
              92
            </span>
          </div>
          <div className="mt-1 text-xs font-medium text-foreground">
            Anthropic ships Claude Opus 4.8
          </div>
          <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
            4 outlets · LLMs
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        {STAGES.map((label) => (
          <span key={label} className="inline-flex items-center gap-1.5">
            <span className="size-1 rounded-full bg-emerald-500" />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function PipelineAnimation() {
  const reduce = useReducedMotion();
  if (reduce) return <PipelineStatic />;

  return (
    <div className="flex flex-col gap-3">
      <div className="relative h-64 w-full overflow-hidden rounded-xl border border-border/60 bg-card/40 sm:h-72">
        {CHIPS.map((chip) => (
          <Chip key={chip.source} chip={chip} />
        ))}
        <SignalCard />
      </div>
      <StageLabels />
    </div>
  );
}
