import {
  ArchitectureDiagram,
  MergeRuleDiagram,
  PipelineDiagram,
} from "@/components/engineering/diagrams";
import { PipelineStages } from "@/components/how-it-works/pipeline-stages";
import { Reveal } from "@/components/reveal";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export const metadata = {
  title: "Engineering notes | Watcher",
  description:
    "How Watcher was built, in order, including the decisions that were wrong and what the measurements changed.",
};

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

export default function Engineering() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-14 px-4 py-6 sm:px-6 sm:py-8">
      <SiteHeader />

      <header className="flex flex-col gap-3">
        <h1 className="text-balance text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
          Engineering notes
        </h1>
        <p className="max-w-[68ch] text-pretty leading-relaxed text-muted-foreground">
          Everything below is in the order it actually happened, including the decisions
          that turned out to be wrong, because those are the ones worth reading about.
        </p>
      </header>

      <Reveal className="card-surface flex flex-col gap-4 rounded-lg p-6">
        <h2 className="text-lg font-semibold tracking-tight">
          The honest part, first
        </h2>
        <div className="flex max-w-[68ch] flex-col gap-4 leading-relaxed text-muted-foreground">
          <p>
            I started this to teach myself how AI systems fit together end to end, and
            it ended up tuned around the things I read. The sources are my sources. The
            relevance scoring is my opinion about what is worth knowing on a given day,
            and the noise rules are my opinion about what counts as substance rather
            than commentary. So if you open the front page and the stories look
            unimportant to you, nothing has gone wrong. You are just not the person it
            was tuned for.
          </p>
          <p>
            I am saying that plainly because the alternative is pretending this is a
            product with a market, and that pretense would make every decision below
            harder to read. Building for one known reader also turned out to be the more
            interesting constraint. I could make sharp calls that something built for
            everyone would have to hedge, and most of what is worth reading below comes
            out of being allowed to make them.
          </p>
          <p className="text-foreground">
            So: the feed is the artifact. The engineering is the part that generalizes,
            and it is what the rest of this page is about.
          </p>
        </div>
      </Reveal>

      <Section title="What I was trying to build">
        <p>
          I read a lot of engineering and AI writing, and the problem was never finding
          material. The problem was that the same announcement arrives five times from
          five sources, and the thing I actually want is one paragraph telling me what
          happened and whether it changes anything for me. So the goal was narrow: take
          a firehose of feeds, group the coverage that is about the same event, and put
          one honest summary in front of it.
        </p>
        <p>
          Scope discipline is most of what made this finishable. It is a read-only
          briefing. There is no login, no personalization, and no way for a reader to
          change anything. Every feature I cut was cut because it would have added a
          surface to maintain without improving the thing the project exists to
          demonstrate. A source management screen, to pick one, is a screen for editing
          a comma separated list that lives in an environment variable.
        </p>
      </Section>

      <Section title="The shape of it">
        <p>
          Three processes that never speak to each other directly. A worker writes to
          the database, an API reads from it, and the browser only ever sees the API.
          That separation is what lets the worker be a slow batch job while the page
          stays fast, and it keeps the database credentials on one side of a boundary
          the browser cannot reach.
        </p>
        <ArchitectureDiagram />
        <p>
          The worker is a one-shot script. It runs, it finishes, it exits. That single
          property decided the scheduling, because a job that is idempotent and
          terminates does not need an orchestrator, it needs a trigger. GitHub Actions
          on a cron provides that for free, the schedule lives in version control next
          to the code, and the manual dispatch button doubles as the demo trigger. I
          considered a long-running scheduler process and rejected it, because that is a
          process to keep alive and monitor in exchange for something a cron line
          already does.
        </p>
        <p>
          The browser fetching the API directly rather than through the frontend server
          is also deliberate, and it is the kind of decision that looks arbitrary until
          you see the constraint. The API is public and has no authentication, so the
          only thing standing between it and abuse is a per-address rate limit. Routing
          every reader through one server would collapse every visitor into a single
          address and one shared bucket, which throttles everyone at once the moment one
          person refreshes too fast.
        </p>
      </Section>

      <Section title="The pipeline, and where the money goes">
        <PipelineDiagram />
        <p>
          Seven stages, and the interesting part is the two gates. Before anything
          reaches a model, the batch is filtered against URLs already stored. On the most
          recent run that skipped 120 of 374 articles, which is 120 model calls that
          never happened. The second gate is the noise flag: articles the classifier
          rejects never reach the embedder, which keeps both the vector space and the
          bill smaller.
        </p>
        <p>
          Neither gate is clever. Both are just refusing to do work, which turned out to
          be the entire cost story. The expensive lever in an LLM pipeline is what you
          send, not which model you send it to.
        </p>
      </Section>

      <Reveal className="flex flex-col gap-7">
        <div className="flex max-w-[68ch] flex-col gap-2">
          <h2 className="text-lg font-semibold tracking-tight">Stage by stage</h2>
          <p className="leading-relaxed text-muted-foreground">
            The mechanism first, then the decision behind it.
          </p>
        </div>
        <PipelineStages />
      </Reveal>

      <Section title="Clustering, which is the part I actually care about">
        <p>
          Grouping coverage of the same event is where a naive approach falls apart
          fastest. With a single similarity threshold you get to choose your failure.
          Set it high and one story fragments into five cards. Set it low and unrelated
          stories collapse into one. No value avoids both, because the two distributions
          overlap.
        </p>
        <p>
          What breaks the tie is that similarity is not the only signal available. The
          classifier already returns the named entities of each story, at no additional
          cost, because it was going to read the article anyway. That gives me a sparse
          signal to combine with the dense one.
        </p>
        <MergeRuleDiagram />
        <p>
          The second branch is the entire idea. It lets a merely similar pair join the
          same story when they also name the same company, model or vulnerability. That
          buys recall on one event written up from several angles without lowering the
          similarity floor for everything else, which is precisely what a single
          threshold cannot do.
        </p>
        <p>
          Being honest about the weakness: this rule was tuned on a news-heavy corpus,
          where a shared entity reliably meant a shared event because ten outlets were
          covering one announcement. The feed mix has since moved toward long-form
          engineering blogs, and on those a shared entity frequently means a shared
          author instead. The rule now produces publisher digests more often than it
          should. I have not hand-tuned it in response, because the correct move is to
          rebuild the labelled pairs from the current data and let the eval decide.
          Reaching for the threshold first would be guessing with extra steps.
        </p>
      </Section>

      <Section title="I built the eval before I built the interface">
        <p>
          The classifier decides what enters the product, so a bad one is not a quality
          problem, it is a product that quietly shows the wrong things. Tests prove the
          code runs. They do not prove the judgement is any good. So before writing a
          single page, I hand-labelled fifty articles, balanced across topics, and wrote
          a harness that scores the classifier against them and exits non-zero when it
          falls below a fixed bar.
        </p>
        <p>
          Labelled by hand specifically, and not by a model. The classifier is Claude.
          Grading Claude with Claude means the grader inherits the same blind spots as
          the thing it is grading, and the number that comes out is a measurement of
          agreement rather than a measurement of correctness.
        </p>
        <p>
          The pass bar is deliberately lopsided. It has to be right at least ninety
          percent of the time when it calls something noise, but it is allowed to miss
          things. Those two errors are not symmetric. A false positive throws away a
          good story permanently, and a false negative just means one extra item to
          scroll past. I set the bar around the failure I could not take back.
        </p>
        <p>
          It earned its place almost immediately. It showed me I was scoring
          low-substance culture posts more or less at random, somewhere between 0.15 and
          0.50 on essentially identical material. The fix was not a better prompt. The
          fix was deleting the category, so material with no real technical or product
          takeaway has nowhere to be filed and falls through to noise by construction.
          An eval that only confirms what you already believed is not doing much work.
          This one changed the taxonomy.
        </p>
      </Section>

      <Section title="The measurement that changed the project">
        <p>
          At some point I set a numeric gate for myself. Before writing any chunking or
          retrieval code, at least half the corpus had to contain enough text to be
          worth chunking. Then I measured, and the answer was eleven percent. The median
          article in my own database was 162 characters.
        </p>
        <p>
          My first instinct was to build an HTTP fetcher that would download each article
          and extract the body. I budgeted two days for it. Before starting, I measured
          the feeds themselves, and found the full text was already arriving and I was
          discarding it. The connector was reading the summary field, which publishers
          use for a teaser, and ignoring the content field, which is where they put the
          whole post. The gap was between thirty and sixty-seven times the text
          depending on the feed. One feed was delivering 314 characters where 21,115
          were available.
        </p>
        <p>
          A two day fetcher became a five line change. That is the most useful habit
          this project taught me and it is not a technical one: measure the instrument
          before you trust the reading. I was about to solve a problem I did not have,
          and the only reason I did not is that I had committed to a number in advance
          and had to go and collect it.
        </p>
      </Section>

      <Section title="A tradeoff I had to own rather than solve">
        <p>
          Fixing that bug and swapping the feeds toward long-form engineering blogs took
          the median article from 162 characters to roughly 2,700. It also broke
          something. Long-form engineering posts are single-source by nature. Nobody
          else writes up the same internal migration on the same day. Clustering
          requires at least two members to form a story, so those articles do not
          cluster at all.
        </p>
        <p>
          News feeds cluster beautifully and carry almost no body text. Engineering blogs
          carry enormous body text and do not cluster. The two things I wanted were in
          direct tension inside the same configuration value, and no amount of
          engineering was going to resolve it. I picked the one the next phase depends
          on and wrote down what it cost rather than leaving the old claim standing.
          Multi-outlet event clustering is not currently demonstrable on this corpus,
          and I removed that claim from the front page the day it stopped being true.
        </p>
        <p>
          Later I brought a handful of news feeds back. The blogs were there for
          retrieval, and without news the front page stopped showing the week&apos;s
          actual events, which is the one job the feed has. The two now sit side by
          side: news for grouping coverage, long-form posts for the text.
        </p>
      </Section>

      <Section title="A bug that could only appear in production">
        <p>
          The first run after the feed swap crashed with a 400 from the database
          gateway. The lookup that checks which URLs are already stored was sending
          every URL in a single filter, which the client places in the request URL. At
          roughly 280 articles that produced a query string of about nine kilobytes, and
          the gateway rejected it.
        </p>
        <p>
          The detail I find genuinely useful is that the guard was already written. The
          file contained a constant for the batch size and a comment describing exactly
          the overflow it existed to prevent. The loop that would have used it was never
          written. Reading the file gave false assurance, because the comment described
          correct behaviour sitting directly above code that did not implement it. It
          had worked for the entire life of the project purely because the corpus had
          never been large enough to overflow.
        </p>
        <p>
          The regression test asserts on the observed batch boundaries rather than on
          the set of URLs that comes back. That distinction matters. The obvious
          assertion, that the right URLs were returned, still passes if you delete the
          fix entirely. A test that cannot fail is decoration.
        </p>
      </Section>

      <Section title="What I could not tell you about my own system">
        <p>
          For most of this project I could not have told you what a single run cost. I
          had an estimate written in my decision log, roughly four tenths of a cent per
          article, with no instrumentation behind it. Worse, the table recording each
          run had a status column with a failed value that no code path ever wrote. The
          summary was only constructed after every stage had already succeeded, so a run
          that died partway through left no row at all. The history I could see was a
          sample of the runs that worked.
        </p>
        <p>
          Both are fixed. Failures now write a row carrying the error and the counts
          they reached, and every run records tokens, cost and per-stage wall time. The
          first real numbers were more interesting than I expected. A run costs 1.74
          dollars across 247 articles. Elapsed time is thirty minutes, of which actual
          computation is forty-nine seconds. Fifty-eight percent of the wall clock is my
          own rate limiting, sleeping four seconds between calls, serially.
        </p>
        <p>
          I am leaving it that way, and I want to be clear that this is a choice rather
          than neglect. The rate limit applies to the account rather than the process,
          so serial pacing is three lines of code and physically cannot burst past it. A
          concurrent pool needs a token bucket and backoff logic, and it would save
          roughly twenty minutes on a job that runs every two days on a free runner. If
          latency ever mattered I would move to the batch API instead, which is half the
          price and makes wall clock time somebody else&apos;s problem. The point is
          that I know the number now, and the decision follows from it rather than
          preceding it.
        </p>
      </Section>

      <Section title="The ranking bug I found by looking at the feed">
        <p>
          The front page was showing a model launch from months earlier above the
          week&apos;s actual news. The cause was one timestamp. Momentum weighted each
          article by when the pipeline found it, not when it was published, so the
          first fetch of a blog with years of archive made every old post look like
          breaking news. A cluster could also come back to life when one new article
          joined it.
        </p>
        <p>
          Ranking now uses the publication date, capped so it can never be later than
          the moment the article arrived, which stops a feed with a timezone bug from
          making something look fresher than it is. One function changed, and
          everything downstream picked it up, because the scoring and the staleness
          check were already pure functions that only take a list of times.
        </p>
      </Section>

      <Section title="What is not finished">
        <p>
          Clustering has a small labelled test set that checks whether same-story and
          different-story similarities actually separate. Synthesis has no eval at all,
          which is the largest honest gap in the project, because it is the output a
          reader sees and trusts.
        </p>
        <p>
          Retrieval over article chunks, so every sentence in a summary can be traced
          back to the source text that produced it, is the next real piece of work. That
          is also the point at which I will be able to say something measurable about
          whether the summaries are grounded, rather than only that they look right.
        </p>
      </Section>

      <SiteFooter />
    </main>
  );
}
