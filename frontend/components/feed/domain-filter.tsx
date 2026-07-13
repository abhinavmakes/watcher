"use client";

import { domainMeta } from "@/lib/domains";
import { hexAlpha } from "@/lib/momentum";

interface DomainFilterProps {
  domains: string[];
  active: string | null;
  onSelect: (domain: string | null) => void;
}

export function DomainFilter({ domains, active, onSelect }: DomainFilterProps) {
  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-[11px] uppercase tracking-wider"
      role="group"
      aria-label="Filter by domain"
    >
      <button
        type="button"
        onClick={() => onSelect(null)}
        aria-pressed={active === null}
        className={`transition-colors ${
          active === null
            ? "text-foreground underline decoration-1 underline-offset-4"
            : "text-muted-foreground hover:text-foreground"
        }`}
      >
        All
      </button>

      {domains.map((domain) => {
        const { label, color } = domainMeta(domain);
        const selected = active === domain;
        return (
          <button
            key={domain}
            type="button"
            onClick={() => onSelect(selected ? null : domain)}
            aria-pressed={selected}
            className={`inline-flex items-center gap-1.5 transition-colors ${
              selected
                ? "text-foreground underline decoration-1 underline-offset-4"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <span
              className="size-1.5 shrink-0 rounded-full"
              style={{ backgroundColor: selected ? color : hexAlpha(color, 0.55) }}
            />
            {label}
          </button>
        );
      })}
    </div>
  );
}
