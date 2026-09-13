import {
  ArchitectureDiagram,
  MergeRuleDiagram,
  PipelineDiagram,
} from "@/components/how-it-works/diagrams";
import { PipelineStages } from "@/components/how-it-works/pipeline-stages";
import { Reveal } from "@/components/reveal";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { DECISIONS_URL } from "@/lib/site";

export const metadata = {
  title: "How it works | Watcher",
  description:
    "How Watcher works: architecture, pipeline stages, the clustering rule, ranking, cost, evaluation and the main design decisions.",
};

const LINK_CLASS =
  "font-medium text-foreground underline decoration-foreground/40 underline-offset-4 transition-colors hover:decoration-foreground";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Reveal className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      <div className="flex max-w-[68ch] flex-col gap-4 leading-relaxed text-muted-foreground">
        {children}
      </div>
    </Reveal>
  );
}

export default function HowItWorks() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-14 px-4 py-6 sm:px-6 sm:py-8">
      <SiteHeader />

      <header className="flex flex-col gap-3">
        <h1 className="text-balance text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
          How it works
        </h1>
        <p className="max-w-[68ch] text-pretty leading-relaxed text-muted-foreground">
          Watcher is a weekly batch pipeline. A worker fetches and processes articles,
          writes the results to Postgres, and a read-only API serves this site. The feed
          is tuned to what I read, so the picks are mine. This page documents the system
          behind them.
        </p>
      </header>

      <Section title="Architecture">
        <ArchitectureDiagram />
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            <span className="font-medium text-foreground">Worker.</span> A one-shot
            Python job on GitHub Actions. It runs weekly, processes new articles and
            exits.
          </li>
          <li>
            <span className="font-medium text-foreground">Database.</span> Supabase
            Postgres with pgvector, holding articles, stories and a record of every run.
          </li>
          <li>
            <span className="font-medium text-foreground">API.</span> A read-only
            FastAPI service with per-address rate limiting and no login.
          </li>
          <li>
            <span className="font-medium text-foreground">Site.</span> Next.js on
            Vercel. The browser calls the API on the same domain.
          </li>
        </ul>
      </Section>

      <Section title="Pipeline">
        <PipelineDiagram />
        <PipelineStages />
      </Section>

      <Section title="The clustering rule">
        <MergeRuleDiagram />
        <p>
          A single similarity threshold forces a bad choice. Set it high and one event
          splits into several stories. Set it low and unrelated stories merge. The rule
          has two tiers instead. An article joins an existing story at a similarity of
          0.78 or more, or 0.75 when two new articles form a story. A looser match of
          0.65 or more joins only when both name the same entity, such as a company,
          model or vulnerability, which the classifier has already extracted. That
          catches one event reported from different angles without lowering the bar for
          everything else.
        </p>
      </Section>

      <Section title="Data model">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="py-2 pr-4 text-left font-medium text-foreground">
                  Table
                </th>
                <th className="py-2 pr-4 text-left font-medium text-foreground">
                  Holds
                </th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border">
                <td className="py-2 pr-4">
                  <code>articles</code>
                </td>
                <td className="py-2 pr-4">
                  One row per article: source, URL, body text, publication date,
                  classifier output and embedding
                </td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-2 pr-4">
                  <code>clusters</code>
                </td>
                <td className="py-2 pr-4">
                  One row per story: headline, summary, takeaway, average vector,
                  entities, topics, momentum score and status
                </td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-2 pr-4">
                  <code>cluster_articles</code>
                </td>
                <td className="py-2 pr-4">
                  Which articles belong to which story, and when each one joined
                </td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-2 pr-4">
                  <code>pipeline_runs</code>
                </td>
                <td className="py-2 pr-4">
                  One row per run, including failed runs: counts, cost, tokens and time
                  per stage
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Cost and speed">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="py-2 pr-4 text-left font-medium text-foreground">
                  Measure
                </th>
                <th className="py-2 pr-4 text-left font-medium text-foreground">
                  Value
                </th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border">
                <td className="py-2 pr-4">
                  Articles fetched, classified, already stored
                </td>
                <td className="py-2 pr-4">374, 247, 120</td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-2 pr-4">Cost</td>
                <td className="py-2 pr-4">$1.74</td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-2 pr-4">Tokens in, out</td>
                <td className="py-2 pr-4">1,214,709, 50,633</td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-2 pr-4">Wall clock</td>
                <td className="py-2 pr-4">30 minutes</td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-2 pr-4">
                  Fetch, classify, embed, cluster, synthesize, rank
                </td>
                <td className="py-2 pr-4">29s, 1,526s, 10s, 2s, 232s, 8s</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          Measured on the 12 September 2026 run, before the news feeds and headline
          rewrites were added. About 58% of the wall clock is deliberate pacing between
          model calls. The computation itself takes under a minute.
        </p>
      </Section>

      <Section title="How quality is checked">
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            <span className="font-medium text-foreground">Classifier.</span> 50
            hand-labelled articles, balanced across topics. The eval fails below its
            bar: noise precision of at least 0.90 and recall of at least 0.75. Precision
            is held higher because dropping a good story is the worse mistake. The
            labels are written by hand because the classifier is Claude, and grading
            Claude with Claude measures agreement rather than correctness.
          </li>
          <li>
            <span className="font-medium text-foreground">Clustering.</span> 13
            labelled article pairs check that same-story and different-story
            similarities separate at the configured thresholds.
          </li>
        </ul>
      </Section>

      <Section title="Decisions worth explaining">
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            <span className="font-medium text-foreground">
              Stories are ranked by publication date, not fetch date.
            </span>{" "}
            A blog fetched for the first time returns years of archive, and scoring by
            fetch time made those posts rank as new. Each article is dated by the
            earlier of its publication date and the moment it arrived, which also stops
            a feed with a timezone error from looking fresher than it is.
          </li>
          <li>
            <span className="font-medium text-foreground">
              A story stops accepting articles seven days after its first one.
            </span>{" "}
            Without a limit, a large story kept absorbing anything that shared a broad
            name like a lab, and its average vector drifted toward general AI news. The
            window is measured from the first article because measuring from the newest
            would let a story extend its own lifetime every time something joined.
          </li>
          <li>
            <span className="font-medium text-foreground">
              Headlines are rewritten when a story grows.
            </span>{" "}
            A headline written once goes stale as a story gains articles. Growing
            stories are resent to the model with their eight newest articles, which
            keeps the title accurate and caps the cost of each rewrite.
          </li>
          <li>
            <span className="font-medium text-foreground">
              Similarity is computed by hand, not with a clustering library.
            </span>{" "}
            The merge rule is the most opinionated part of the system, and a library
            would hide it behind its own algorithm. The whole clustering stage takes
            about two seconds, so performance gives no reason to trade away that
            control.
          </li>
          <li>
            <span className="font-medium text-foreground">
              Model calls run one at a time.
            </span>{" "}
            The provider&apos;s rate limit applies to the account, so pacing calls four
            seconds apart cannot exceed it. A concurrent pool would need a token bucket
            and retry logic to save about twenty minutes on a weekly job. If speed ever
            matters, the batch API is the better upgrade at half the price.
          </li>
        </ul>
      </Section>

      <Section title="Known limitations">
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            Synthesis has no eval, so summary quality is checked by reading rather than
            measured.
          </li>
          <li>
            The entity rule was tuned on news. On single-publisher blogs a shared entity
            can simply mean the same publisher, so digest stories still form.
          </li>
          <li>
            A story still developing after seven days continues as a new card, so one
            event can appear twice until the older card goes stale.
          </li>
          <li>
            The clustering eval&apos;s pairs come from an earlier, news-heavy corpus and
            do not yet reflect the current feed mix.
          </li>
          <li>
            Google News links are redirects, so one article can arrive directly and
            through Google News and count as two sources.
          </li>
        </ul>
      </Section>

      <p className="max-w-[68ch] text-pretty leading-relaxed text-muted-foreground">
        The history behind these choices, including the ones that were wrong the first
        time, is recorded in{" "}
        <a
          href={DECISIONS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className={LINK_CLASS}
        >
          DECISIONS.md
        </a>
        .
      </p>

      <SiteFooter />
    </main>
  );
}
