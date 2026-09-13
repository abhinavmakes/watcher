import { GithubMark } from "@/components/github-mark";
import { GITHUB_URL } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="flex flex-col gap-3 border-t border-border pt-6 text-[13px] text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
      <span>Watcher. An AI news feed, built in the open.</span>
      <a
        href={GITHUB_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 transition-colors hover:text-foreground"
      >
        <GithubMark className="size-3.5" />
        github.com/abhinavmakes/watcher
      </a>
    </footer>
  );
}
