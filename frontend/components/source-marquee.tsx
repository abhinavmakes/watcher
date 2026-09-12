// A slow horizontal marquee of the outlets Watcher reads. Track holds two copies of
// the list and translates -50% so it loops seamlessly; pauses on hover; edges fade
// out; static under prefers-reduced-motion. Kept in sync with RSS_FEED_URLS + HN —
// update both if the feed list changes.
const TOTAL_FEEDS = 19;
const SOURCES = [
  { name: "Hacker News", url: "https://news.ycombinator.com" },
  { name: "Latent Space", url: "https://www.latent.space" },
  { name: "Chip Huyen", url: "https://huyenchip.com" },
  { name: "Interconnects", url: "https://www.interconnects.ai" },
  { name: "Answer.AI", url: "https://www.answer.ai" },
  { name: "Hamel Husain", url: "https://hamel.dev" },
  { name: "Ahead of AI", url: "https://magazine.sebastianraschka.com" },
  { name: "Simon Willison", url: "https://simonwillison.net" },
  { name: "Lilian Weng", url: "https://lilianweng.github.io" },
  { name: "BAIR", url: "https://bair.berkeley.edu/blog/" },
  { name: "The Pragmatic Engineer", url: "https://newsletter.pragmaticengineer.com" },
  { name: "AWS Machine Learning", url: "https://aws.amazon.com/blogs/machine-learning/" },
  { name: "AWS Architecture", url: "https://aws.amazon.com/blogs/architecture/" },
  { name: "Meta Engineering", url: "https://engineering.fb.com" },
  { name: "Google AI Blog", url: "https://ai.googleblog.com" },
  { name: "Cloudflare", url: "https://blog.cloudflare.com" },
  { name: "Netflix Tech", url: "https://netflixtechblog.com" },
  { name: "Julia Evans", url: "https://jvns.ca" },
  { name: "GitHub Blog", url: "https://github.blog" },
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
