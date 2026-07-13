// Global key that decodes the heat color once, so every momentum number in the
// feed is self-explanatory (and it works on mobile, where the hover tooltip can't).
export function MomentumLegend() {
  return (
    <div className="inline-flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
      <span className="text-foreground">Momentum</span>
      <span>cool</span>
      <span
        className="h-1.5 w-20 rounded-full"
        style={{
          background:
            "linear-gradient(90deg, hsl(210 85% 58%), hsl(110 85% 58%), hsl(10 85% 58%))",
        }}
        aria-hidden
      />
      <span>hot</span>
      <span className="text-border">·</span>
      <span>0–100 — click any card for the synthesis + sources</span>
    </div>
  );
}
