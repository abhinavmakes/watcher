// One quiet line explaining the only number on the page. Replaces the old gradient
// key: if the number needs a colour chart to be legible, the number is the problem.
export function MomentumLegend() {
  return (
    <p className="text-[13px] text-muted-foreground">
      The number on each card is its{" "}
      <span className="font-medium text-foreground">momentum</span>, scored 0 to 100. It
      rises as more sources pile onto a story and fades as those articles get older, so the
      top of the feed is whatever is moving right now.
    </p>
  );
}
