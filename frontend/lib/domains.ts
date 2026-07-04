import {
  Banknote,
  Bot,
  BrainCircuit,
  Briefcase,
  Cpu,
  FileCode,
  FlaskConical,
  GitFork,
  HardDrive,
  Library,
  Rocket,
  Server,
  ShieldAlert,
  Wrench,
  type LucideIcon,
} from "lucide-react";

export interface DomainMeta {
  label: string;
  color: string;
  Icon: LucideIcon;
}

const DOMAINS: Record<string, DomainMeta> = {
  ai_agents: { label: "AI Agents", color: "#8b5cf6", Icon: Bot },
  llms: { label: "LLMs", color: "#6366f1", Icon: BrainCircuit },
  dev_tools: { label: "Dev Tools", color: "#06b6d4", Icon: Wrench },
  open_source: { label: "Open Source", color: "#10b981", Icon: GitFork },
  libraries: { label: "Libraries", color: "#14b8a6", Icon: Library },
  infra: { label: "Infra", color: "#f59e0b", Icon: Server },
  funding: { label: "Funding", color: "#22c55e", Icon: Banknote },
  startups: { label: "Startups", color: "#f43f5e", Icon: Rocket },
  research: { label: "Research", color: "#3b82f6", Icon: FlaskConical },
  security: { label: "Security", color: "#ef4444", Icon: ShieldAlert },
  python: { label: "Python", color: "#eab308", Icon: FileCode },
  systems: { label: "Systems", color: "#a855f7", Icon: Cpu },
  hardware: { label: "Hardware", color: "#ec4899", Icon: HardDrive },
  business: { label: "Business", color: "#64748b", Icon: Briefcase },
};

const FALLBACK_COLOR = "#94a3b8";

function prettify(value: string): string {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function domainMeta(domain: string): DomainMeta {
  return (
    DOMAINS[domain] ?? { label: prettify(domain), color: FALLBACK_COLOR, Icon: Bot }
  );
}
