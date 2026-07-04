import { PipelineFlow } from "@/components/home/pipeline-flow";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export const metadata = {
  title: "How it works — Watcher",
};

export default function HowItWorks() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader />

      <section className="flex flex-col gap-6 py-8">
        <div className="flex flex-col gap-2">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
            How it works
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">
            From firehose to signal in six stages
          </h1>
          <p className="max-w-2xl text-muted-foreground">
            A batch pipeline runs once a day. Each stage narrows raw coverage into
            ranked, synthesized clusters.
          </p>
        </div>
        <PipelineFlow />
      </section>

      <section className="flex flex-col gap-6 border-t border-border/60 py-8">
        <div className="flex flex-col gap-2">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Scope
          </p>
          <h2 className="text-2xl font-semibold tracking-tight">
            Honest about what this is
          </h2>
        </div>
        <div className="grid gap-8 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <span className="font-mono text-xs uppercase tracking-wider text-emerald-400">
              Live now
            </span>
            <p className="text-sm leading-relaxed text-muted-foreground">
              A public, read-only briefing — no account, no tracking. Daily
              ingestion, entity-anchored clustering, LLM synthesis, and momentum
              scoring over Hacker News and curated RSS.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
              Roadmap
            </span>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Chat with a cluster, personalization, and more sources are planned.
              This is the read-only core — not the full product.
            </p>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
