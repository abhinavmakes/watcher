import { FlaskConical } from "lucide-react";

import { PipelineFlow } from "@/components/home/pipeline-flow";
import { PipelineStages } from "@/components/how-it-works/pipeline-stages";
import { Reveal } from "@/components/reveal";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export const metadata = {
  title: "How it works — Watcher",
};

export default function HowItWorks() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-10 px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader />

      <section className="flex flex-col gap-4 py-2">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
          How it works
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          From a firehose of feeds to a ranked briefing.
        </h1>
        <p className="max-w-2xl text-pretty leading-relaxed text-muted-foreground">
          The whole thing is a batch pipeline that runs once a day. Here&apos;s each
          stage — what it does, and the decision behind it, since the decisions are
          the part that took the time.
        </p>
        <div className="pt-2">
          <PipelineFlow />
        </div>
      </section>

      <section className="flex flex-col gap-6">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <h2 className="text-xl font-semibold tracking-tight">The build, stage by stage</h2>
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            raw feeds → ranked signal
          </span>
        </div>
        <PipelineStages />
      </section>

      <Reveal className="flex flex-col gap-3 rounded-xl border border-emerald-500/25 bg-emerald-500/[0.04] p-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <FlaskConical className="size-4 text-emerald-400" aria-hidden />
          <h2 className="text-lg font-semibold tracking-tight">How I know it works</h2>
          <span className="font-mono text-[11px] uppercase tracking-wider text-emerald-400/80">
            evals, not vibes
          </span>
        </div>
        <p className="max-w-2xl text-pretty leading-relaxed text-muted-foreground">
          I didn&apos;t want to just eyeball outputs, so the classifier has a real
          eval: 50 articles, class-balanced, hand-labeled by me — not by a model,
          because grading Claude with Claude is circular and shares its blind spots.
          The targets are deliberately asymmetric — noise precision above 0.90, higher
          than recall — because a false positive means dropping a good story, and
          that&apos;s the failure the product can&apos;t afford. That eval already paid
          off once: it caught me tagging low-substance &ldquo;culture&rdquo; items
          almost at random, so I cut the domain entirely and let them fall to noise.
        </p>
        <p className="max-w-2xl text-pretty leading-relaxed text-muted-foreground">
          The honest gap: clustering and synthesis don&apos;t have formal evals yet.
          I&apos;ve verified the thresholds separate on real article pairs, but a
          proper hard-negative clustering eval and an LLM-as-judge synthesis eval are
          still on the list.
        </p>
      </Reveal>

      <Reveal className="flex flex-col gap-6">
        <h2 className="text-xl font-semibold tracking-tight">
          What&apos;s live, what&apos;s next
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-2 rounded-xl border border-border/60 bg-card/40 p-5">
            <span className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-emerald-400">
              <span className="size-1.5 rounded-full bg-emerald-500" />
              Live now
            </span>
            <p className="text-sm leading-relaxed text-muted-foreground">
              A public, read-only briefing — no login, no tracking. The daily pipeline,
              entity-anchored clustering, LLM synthesis, and momentum scoring all run
              over Hacker News and curated RSS, served through a rate-limited public
              API the browser talks to directly.
            </p>
          </div>
          <div className="flex flex-col gap-2 rounded-xl border border-border/60 bg-card/40 p-5">
            <span className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-muted-foreground">
              <span className="size-1.5 rounded-full bg-muted-foreground/60" />
              Roadmap
            </span>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Chat with a cluster, personalization, more sources, momentum over time,
              and the evals above are what I&apos;d build next. This is the read-only
              core — not the finished product.
            </p>
          </div>
        </div>
      </Reveal>

      <SiteFooter />
    </main>
  );
}
