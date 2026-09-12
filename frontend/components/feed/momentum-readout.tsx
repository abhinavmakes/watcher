import { momentumColor } from "@/lib/momentum";

interface MomentumReadoutProps {
  value: number;
  size?: "md" | "lg";
}

// Momentum is the one place colour carries meaning on a card, so it is the only
// coloured thing and the only monospace thing. The meter bar that used to sit under
// the number is gone: it encoded exactly what the number already said.
export function MomentumReadout({ value, size = "md" }: MomentumReadoutProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const rounded = Math.round(clamped);

  return (
    <span
      className={`shrink-0 font-mono font-medium leading-none tabular-nums ${
        size === "lg" ? "text-4xl" : "text-3xl"
      }`}
      style={{ color: momentumColor(clamped) }}
      role="img"
      aria-label={`Momentum ${rounded} out of 100`}
      title={`Momentum ${rounded} of 100. How many sources are converging on this story.`}
    >
      {rounded}
    </span>
  );
}
