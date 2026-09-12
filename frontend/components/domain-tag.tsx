import { domainMeta } from "@/lib/domains";

export function DomainTag({ domain }: { domain: string }) {
  return (
    <span className="text-[13px] text-muted-foreground">
      {domainMeta(domain).label}
    </span>
  );
}
