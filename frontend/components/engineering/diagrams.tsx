// Hand-drawn SVG rather than a diagram library: AGENTS.md rules visualizations are
// custom SVG, and a 1.5MB renderer for three static figures is a poor trade on a page
// whose point is that it loads fast. Everything below inherits the site tokens, so the
// figures stay consistent with the rest of the design.

const BOX = "fill-[var(--card)] stroke-[var(--border)]";
const LABEL = "fill-[var(--foreground)] text-[11px] font-medium";
const SUB = "fill-[var(--muted-foreground)] text-[10px]";
const LINE = "stroke-[var(--border)]";

function Figure({
  caption,
  viewBox,
  children,
}: {
  caption: string;
  viewBox: string;
  children: React.ReactNode;
}) {
  return (
    <figure className="flex flex-col gap-3">
      <div className="card-surface overflow-x-auto rounded-lg p-5">
        <svg
          viewBox={viewBox}
          className="h-auto w-full min-w-[520px]"
          role="img"
          aria-label={caption}
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" className="fill-[var(--border)]" />
            </marker>
          </defs>
          {children}
        </svg>
      </div>
      <figcaption className="text-[13px] text-muted-foreground">{caption}</figcaption>
    </figure>
  );
}

function Node({
  x,
  y,
  w = 132,
  h = 44,
  title,
  sub,
}: {
  x: number;
  y: number;
  w?: number;
  h?: number;
  title: string;
  sub?: string;
}) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx="6" className={BOX} strokeWidth="1" />
      <text
        x={x + w / 2}
        y={sub ? y + h / 2 - 3 : y + h / 2 + 4}
        textAnchor="middle"
        className={LABEL}
      >
        {title}
      </text>
      {sub && (
        <text x={x + w / 2} y={y + h / 2 + 12} textAnchor="middle" className={SUB}>
          {sub}
        </text>
      )}
    </g>
  );
}

function Arrow({ d }: { d: string }) {
  return <path d={d} className={LINE} strokeWidth="1" fill="none" markerEnd="url(#arrow)" />;
}

function EdgeLabel({ x, y, text }: { x: number; y: number; text: string }) {
  return (
    <text x={x} y={y} textAnchor="middle" className={SUB}>
      {text}
    </text>
  );
}

export function ArchitectureDiagram() {
  return (
    <Figure
      viewBox="0 0 720 300"
      caption="Three processes that never talk to each other directly. The worker writes, the API reads, and the browser only ever sees the API."
    >
      <Node x={40} y={20} title="Hacker News" sub="top stories" />
      <Node x={200} y={20} title="22 RSS feeds" sub="news and blogs" />
      <Arrow d="M 106 64 L 106 96" />
      <Arrow d="M 266 64 L 266 96" />

      <Node x={40} y={100} w={292} h={48} title="Ingestion worker" sub="GitHub Actions, one shot, weekly" />
      <Arrow d="M 186 148 L 186 186" />

      <Node x={40} y={190} w={292} h={48} title="Supabase" sub="Postgres with pgvector" />
      <Arrow d="M 332 214 L 396 214" />

      <Node x={400} y={190} w={132} h={48} title="FastAPI" sub="read only, rate limited" />
      <Arrow d="M 466 190 L 466 152" />

      <Node x={400} y={100} w={132} h={48} title="Next.js" sub="Vercel" />
      <Arrow d="M 532 124 L 596 124" />
      <Node x={600} y={100} w={80} h={48} title="Browser" />

      <EdgeLabel x={560} y={116} text="fetch" />
      <EdgeLabel x={364} y={208} text="read" />
    </Figure>
  );
}

export function PipelineDiagram() {
  const stages = [
    { t: "Fetch", s: "concurrent" },
    { t: "Dedup", s: "by URL" },
    { t: "Classify", s: "Haiku" },
    { t: "Embed", s: "768d" },
    { t: "Cluster", s: "cosine" },
    { t: "Synthesize", s: "Sonnet" },
    { t: "Rank", s: "decay sum" },
  ];
  return (
    <Figure
      viewBox="0 0 760 170"
      caption="Two gates do most of the cost control. Articles already in the database never reach the classifier, and noise never reaches the embedder."
    >
      {stages.map((stage, i) => (
        <g key={stage.t}>
          <Node x={8 + i * 108} y={40} w={92} h={44} title={stage.t} sub={stage.s} />
          {i < stages.length - 1 && (
            <Arrow d={`M ${100 + i * 108} 62 L ${114 + i * 108} 62`} />
          )}
        </g>
      ))}
      <Arrow d="M 154 40 L 154 18" />
      <text x={154} y={14} textAnchor="middle" className={SUB}>
        already seen, drop
      </text>
      <Arrow d="M 370 84 L 370 108" />
      <text x={370} y={122} textAnchor="middle" className={SUB}>
        noise, drop
      </text>
    </Figure>
  );
}

export function MergeRuleDiagram() {
  return (
    <Figure
      viewBox="0 0 720 280"
      caption="The second branch is the whole idea. It buys recall on one event covered from several angles without lowering the similarity floor for everything else."
    >
      <Node x={284} y={12} w={152} h={40} title="New article" sub="vs an existing story" />
      <Arrow d="M 360 52 L 360 78" />

      <Node x={274} y={82} w={172} h={40} title="similarity ≥ 0.78 ?" />
      <Arrow d="M 274 102 L 196 102" />
      <EdgeLabel x={234} y={94} text="yes" />
      <Arrow d="M 360 122 L 360 152" />
      <EdgeLabel x={378} y={142} text="no" />

      <Node x={44} y={82} w={148} h={40} title="Join the story" />

      <Node x={228} y={156} w={264} h={44} title="similarity ≥ 0.65 and shares an entity ?" />
      <Arrow d="M 228 178 L 196 178" />
      <EdgeLabel x={212} y={170} text="yes" />
      <Arrow d="M 360 200 L 360 228" />
      <EdgeLabel x={378} y={218} text="no" />

      <Node x={44} y={156} w={148} h={44} title="Join the story" sub="same event, new angle" />
      <Node x={274} y={232} w={172} h={40} title="Start a new story" />
    </Figure>
  );
}
