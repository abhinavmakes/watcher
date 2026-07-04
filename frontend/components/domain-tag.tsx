import { domainMeta } from "@/lib/domains";

export function DomainTag({ domain }: { domain: string }) {
  const { label, color } = domainMeta(domain);
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
      <span
        className="size-1.5 shrink-0 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}
