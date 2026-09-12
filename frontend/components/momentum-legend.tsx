// One quiet line explaining the only number on the page. Replaces the old gradient
// key: if the number needs a colour chart to be legible, the number is the problem.
export function MomentumLegend() {
  return (
    <p className="text-[13px] text-muted-foreground">
      The number on each story is its{" "}
      <span className="font-medium text-foreground">momentum</span>: roughly how many
      sources landed on it, on a scale of 0 to 100. More coverage floats higher.
    </p>
  );
}
