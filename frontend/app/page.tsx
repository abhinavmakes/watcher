import Link from "next/link";

import { FeedView } from "@/components/feed/feed-view";
import { StoryFold } from "@/components/home/story-fold";
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
      {/* Three weights, not one grey block: the claim, then why it exists, then how it
          works. The legend stays last because it describes the cards, not the project. */}
      <section className="flex max-w-2xl flex-col gap-3">
        <h1 className="text-balance text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
          An AI news feed that does the reading for you.
        </h1>
        <p className="text-pretty text-[15px] leading-relaxed text-foreground sm:text-base">
          Watcher is a system I built to stop reading the same AI and software
          engineering story five times over.
        </p>
        <p className="text-pretty text-sm leading-relaxed text-muted-foreground">
          Every week it pulls in everything new across AI and software engineering, scores each
          article for relevance and drops the noise, then embeds what survives and
          clusters it by meaning rather than by keyword, so a dozen write-ups of one
          launch collapse into a single story. Each story gets a synthesized briefing and
          a momentum score that weights fresh coverage and lets older coverage decay.
          What you read is one card per story instead of five versions of it.
        </p>
        <MomentumLegend />
      </section>

      <FeedView />

      <section className="flex flex-col gap-5 border-t border-border pt-10">
        <div className="flex max-w-2xl flex-col gap-2">
          <h2 className="text-lg font-semibold tracking-tight">
            Many outlets, one story
          </h2>
          <p className="text-pretty leading-relaxed text-muted-foreground">
            The same news breaks everywhere at once. Watcher reads all of it, works out
            which articles are about the same event, and writes one card.{" "}
            <Link
              href="/how-it-works"
              className="font-medium text-foreground underline decoration-foreground/40 underline-offset-4 transition-colors hover:decoration-foreground"
            >
              See how it works
            </Link>{" "}
            for every stage and the reasoning behind it.
          </p>
        </div>
        <StoryFold />
      </section>

      <SiteFooter />
    </main>
  );
}
