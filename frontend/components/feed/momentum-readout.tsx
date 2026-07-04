import { momentumColor } from "@/lib/momentum";

interface MomentumReadoutProps {
  value: number;
  size?: "md" | "lg";
}

// Momentum as a monospace signal-strength readout: a big heat-colored number over a
// slim fill meter. A hover tooltip explains what the number means; the global
// MomentumLegend covers the same on touch devices.
export function MomentumReadout({ value, size = "md" }: MomentumReadoutProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const rounded = Math.round(clamped);
  const color = momentumColor(clamped);
  const numberClass = size === "lg" ? "text-6xl" : "text-4xl";
  const meterWidth = size === "lg" ? "w-16" : "w-12";

  return (
    <div
      className="group/mom relative flex flex-col items-end gap-1.5"
      role="img"
      aria-label={`Momentum ${rounded} of 100`}
    >
      <span
        className={`font-mono font-semibold leading-none tabular-nums ${numberClass}`}
        style={{ color }}
      >
        {rounded}
      </span>
      <div className={`h-1 overflow-hidden rounded-full bg-border ${meterWidth}`}>
        <div
          className="h-full rounded-full"
          style={{ width: `${clamped}%`, backgroundColor: color }}
        />
      </div>

      <div
        aria-hidden
        className="pointer-events-none absolute right-0 top-full z-20 mt-2 hidden w-56 rounded-lg border border-border bg-popover p-3 text-left text-[11px] font-normal leading-relaxed tracking-normal normal-case text-popover-foreground shadow-xl group-hover/mom:block"
      >
        <span className="font-mono font-semibold" style={{ color }}>
          Momentum {rounded}/100
        </span>{" "}
        <span className="text-muted-foreground">
          — how much live coverage is converging on this story. Cooler is quiet;
          hotter means more sources.
        </span>
      </div>
    </div>
  );
}
