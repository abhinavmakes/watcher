import { GithubMark } from "@/components/github-mark";
import { GITHUB_URL } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="flex flex-col gap-3 border-t border-border/60 py-8 sm:flex-row sm:items-center sm:justify-between">
      <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
        Watcher · daily AI briefing
      </span>
      <a
        href={GITHUB_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
      >
        <GithubMark className="size-3.5" />
        github.com/abhinavmakes/watcher
      </a>
    </footer>
  );
}
