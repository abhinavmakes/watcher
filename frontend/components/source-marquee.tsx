// A slow horizontal marquee of the outlets Watcher reads. Track holds two copies of
// the list and translates -50% so it loops seamlessly; pauses on hover; edges fade
// out; static under prefers-reduced-motion. Representative real names/URLs — set
// SOURCES to your actual RSS_FEED_URLS list so it matches what the pipeline fetches.
const TOTAL_FEEDS = 21;
const SOURCES = [
  { name: "Hacker News", url: "https://news.ycombinator.com" },
  { name: "The Verge", url: "https://www.theverge.com" },
  { name: "Ars Technica", url: "https://arstechnica.com" },
  { name: "TechCrunch", url: "https://techcrunch.com" },
  { name: "VentureBeat", url: "https://venturebeat.com" },
  { name: "MIT Tech Review", url: "https://www.technologyreview.com" },
  { name: "arXiv", url: "https://arxiv.org" },
  { name: "Hugging Face", url: "https://huggingface.co/blog" },
  { name: "Anthropic", url: "https://www.anthropic.com/news" },
  { name: "OpenAI", url: "https://openai.com/news" },
  { name: "Google AI", url: "https://blog.google/technology/ai/" },
  { name: "Simon Willison", url: "https://simonwillison.net" },
];

export function SourceMarquee() {
  const items = [...SOURCES, ...SOURCES];
  return (
    <div className="flex flex-col gap-2 border-t border-border/60 pt-5">
      <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        Reading from{" "}
        <span className="text-foreground tabular-nums">{TOTAL_FEEDS}</span> sources
      </span>
      <div className="relative overflow-hidden [-webkit-mask-image:linear-gradient(to_right,transparent,#000_6%,#000_94%,transparent)] [mask-image:linear-gradient(to_right,transparent,#000_6%,#000_94%,transparent)]">
        <div className="flex w-max animate-[marquee_40s_linear_infinite] items-center gap-x-8 pr-8 hover:[animation-play-state:paused] motion-reduce:animate-none">
          {items.map((source, i) => {
            const isClone = i >= SOURCES.length;
            return (
              <a
                key={i}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-hidden={isClone}
                tabIndex={isClone ? -1 : 0}
                className="whitespace-nowrap font-mono text-xs text-muted-foreground underline-offset-2 transition-colors hover:text-foreground hover:underline"
              >
                {source.name}
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
}
