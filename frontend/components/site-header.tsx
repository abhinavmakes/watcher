import Link from "next/link";

import { GithubMark } from "@/components/github-mark";
import { GITHUB_URL } from "@/lib/site";

export function SiteHeader() {
  return (
    <header className="flex items-center justify-between gap-4 border-b border-border/60 pb-4">
      <Link href="/" className="flex items-baseline gap-3">
        <span className="font-mono text-sm font-semibold tracking-[0.25em] text-foreground">
          WATCHER
        </span>
        <span className="hidden text-sm text-muted-foreground sm:inline">
          The daily AI briefing
        </span>
      </Link>
      <nav className="flex items-center gap-5 font-mono text-xs uppercase tracking-wider text-muted-foreground">
        <Link
          href="/how-it-works"
          className="transition-colors hover:text-foreground"
        >
          How it works
        </Link>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 transition-colors hover:text-foreground"
        >
          <GithubMark className="size-3.5" />
          Source
        </a>
      </nav>
    </header>
  );
}
