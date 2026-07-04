// Continuous hot→cool scale: high momentum reads hot (red/orange), low reads cool
// (blue). No time series here, so this encodes level, not trend. `alpha` < 1 emits
// the modern `hsl(H S L / A)` form — pass it directly as a CSS color (do NOT run the
// result through hexAlpha, which is hex-only).
export function momentumColor(value: number, alpha = 1): string {
  const clamped = Math.max(0, Math.min(100, value));
  const hue = (210 - (clamped / 100) * 200).toFixed(0);
  const a = Math.max(0, Math.min(1, alpha));
  return a >= 1 ? `hsl(${hue} 85% 58%)` : `hsl(${hue} 85% 58% / ${a})`;
}

// Append an alpha channel to a 6-digit hex color (domain accents are all #rrggbb).
export function hexAlpha(hex: string, alpha: number): string {
  const clamped = Math.max(0, Math.min(1, alpha));
  const suffix = Math.round(clamped * 255)
    .toString(16)
    .padStart(2, "0");
  return `${hex}${suffix}`;
}
