import { FeedView } from "@/components/feed/feed-view";
import { PipelineAnimation } from "@/components/home/pipeline-animation";
import { MomentumLegend } from "@/components/momentum-legend";
import { SiteHeader } from "@/components/site-header";
import { SourceMarquee } from "@/components/source-marquee";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader />

      <section className="grid gap-8 lg:grid-cols-[1fr_1.05fr] lg:items-center">
        <div className="flex flex-col gap-4">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
            AI &amp; tech · updated daily
          </p>
          <h1 className="text-balance text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
            The AI &amp; tech stories everyone&apos;s covering right now.
          </h1>
          <p className="text-pretty leading-relaxed text-muted-foreground">
            Watcher reads 20+ AI and tech sources, throws out the low-quality noise,
            and groups the outlets covering the same story. The more outlets pile onto
            one thing, the more it matters — so it rises to the top, each with a plain
            summary and a “so what.” Sources are one click away.
          </p>
          <MomentumLegend />
        </div>
        <PipelineAnimation />
      </section>

      <SourceMarquee />

      <FeedView />
    </main>
  );
}
