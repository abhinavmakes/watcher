import Link from "next/link";

import { FeedView } from "@/components/feed/feed-view";
import { PipelineAnimation } from "@/components/home/pipeline-animation";
import { MomentumLegend } from "@/components/momentum-legend";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-6 sm:px-6 sm:py-8">
      <SiteHeader />

      {/* Content first. The explainer used to sit above the feed — a hero, a paragraph,
          a legend, an animation and a logo marquee — so the first thing a visitor met
          was the site describing itself rather than the stories it found. */}
      <section className="flex max-w-2xl flex-col gap-2.5">
        <h1 className="text-balance text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
          An AI news feed that does the reading for you.
        </h1>
        <p className="text-pretty leading-relaxed text-muted-foreground">
          Every week, the system reads twenty-three AI and engineering sources, throws
          out the filler, then uses AI to group the articles covering the same story and
          write one short briefing for each, so you read it once instead of five times.
        </p>
        <MomentumLegend />
        <p className="rounded-md border border-border bg-muted/40 px-3.5 py-2.5 text-[13px] leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">A note.</span> The feed here is
          tuned for me. The sources, the scoring, the clustering rules, all of it is
          shaped around what I happen to care about. So if these stories look a bit
          arbitrary from where you are sitting, that is fair, and it is sort of the
          point. I built this mostly to learn how these systems fit together end to end,
          and that is the half I would actually point you at:{" "}
          <Link
            href="/how-it-works"
            className="font-medium text-foreground underline decoration-foreground/40 underline-offset-4 transition-colors hover:decoration-foreground"
          >
            see how it works
          </Link>
          , which covers every stage and the main decisions behind them.
        </p>
      </section>

      <FeedView />

      <section className="flex flex-col gap-5 border-t border-border pt-10">
        <div className="flex max-w-2xl flex-col gap-2">
          <h2 className="text-lg font-semibold tracking-tight">
            How a story gets here
          </h2>
          <p className="text-pretty leading-relaxed text-muted-foreground">
            Seven stages, start to finish, running on a schedule.{" "}
            <Link
              href="/how-it-works"
              className="font-medium text-foreground underline decoration-foreground/40 underline-offset-4 transition-colors hover:decoration-foreground"
            >
              See how it works
            </Link>{" "}
            for each stage and the reasoning behind it.
          </p>
        </div>
        <PipelineAnimation />
      </section>

      <SiteFooter />
    </main>
  );
}
