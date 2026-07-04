import { FeedView } from "@/components/feed/feed-view";
import { PipelineAnimation } from "@/components/home/pipeline-animation";
import { MomentumLegend } from "@/components/momentum-legend";
import { SiteHeader } from "@/components/site-header";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader />

      <section className="grid gap-8 lg:grid-cols-[1fr_1.05fr] lg:items-center">
        <div className="flex flex-col gap-4">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
            The daily AI intelligence briefing
          </p>
          <h1 className="text-balance text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
            The AI/tech news firehose, ranked by momentum.
          </h1>
          <p className="text-pretty leading-relaxed text-muted-foreground">
            Watcher reads a couple dozen AI/tech feeds, drops the noise, and groups
            every outlet covering the same story. The more outlets on a story, the
            higher it ranks. Click any story for the synthesis and its sources.
          </p>
          <MomentumLegend />
        </div>
        <PipelineAnimation />
      </section>

      <FeedView />
    </main>
  );
}
