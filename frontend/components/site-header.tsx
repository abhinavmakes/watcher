import Link from "next/link";

import { GithubMark } from "@/components/github-mark";
import { GITHUB_URL } from "@/lib/site";

export function SiteHeader() {
  return (
    <header className="flex items-center justify-between gap-4 py-1">
      <Link href="/" className="flex items-baseline gap-2.5">
        <span className="text-[15px] font-semibold tracking-tight text-foreground">
          Watcher
        </span>
        <span className="hidden text-[13px] text-muted-foreground sm:inline">
          a weekly AI briefing
        </span>
      </Link>
      <nav className="flex items-center gap-5 text-[13px] text-muted-foreground">
        <Link href="/engineering" className="transition-colors hover:text-foreground">
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
