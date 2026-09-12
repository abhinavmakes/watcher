import type {
  ClusterArticleRef,
  ClusterCard,
  ClusterDetail,
  ClusterPage,
  RunPage,
} from "@/lib/types";

// Typed mock data matching the read-API contract. Lets the whole UI render before
// a live worker run (clusters are stale → the real feed is empty until a fresh run).
const cards: ClusterCard[] = [
  {
    id: "opus-48-1m-context",
    title: "Anthropic ships Claude Opus 4.8 with a 1M-token context window",
    summary:
      "Anthropic released Claude Opus 4.8, extending the context window to one million tokens and posting gains on agentic coding and long-document reasoning benchmarks. The rollout covers the API and Claude Code, with pricing held flat against the prior Opus tier.",
    so_what:
      "A 1M-token window at the same price collapses the case for elaborate chunking on most RAG stacks — retrieval becomes a cost lever, not a correctness one.",
    momentum: 92.4,
    domains: ["llms", "ai_agents"],
    key_entities: ["Anthropic", "Claude Opus 4.8", "Claude Code"],
    article_count: 6,
    status: "active",
  },
  {
    id: "openai-agent-sdk-leak",
    title: "OpenAI's next agent framework surfaces in an SDK commit",
    summary:
      "A merged commit in OpenAI's public SDK referenced an unannounced agent-orchestration module with built-in tool routing and handoff primitives, prompting speculation ahead of any official launch.",
    so_what:
      "If agent orchestration ships in the first-party SDK, the thin wrapper frameworks lose their main reason to exist — the moat was always the glue, not the model.",
    momentum: 78.1,
    domains: ["ai_agents", "dev_tools"],
    key_entities: ["OpenAI", "agents SDK"],
    article_count: 4,
    status: "active",
  },
  {
    id: "meta-llama-400b-open",
    title: "Meta open-sources a 400B Llama variant under a permissive license",
    summary:
      "Meta published weights for a 400-billion-parameter Llama model with a license that drops the prior monthly-active-user restriction, alongside a smaller distilled checkpoint aimed at single-GPU inference.",
    so_what:
      "A truly permissive frontier-class open weight resets the build-vs-buy math for any team that was renting a closed model purely to avoid the licensing footguns.",
    momentum: 71.6,
    domains: ["open_source", "llms"],
    key_entities: ["Meta", "Llama", "open weights"],
    article_count: 5,
    status: "active",
  },
  {
    id: "cursor-series-c",
    title: "Cursor raises $200M to push agentic coding into larger teams",
    summary:
      "The maker of the Cursor editor closed a $200M round to expand its background-agent product and enterprise controls, citing rapid adoption among engineering orgs standardizing on AI-assisted workflows.",
    so_what:
      "The funding is a bet that the IDE, not the chat box, is where coding agents get adopted — distribution through the editor beats yet another standalone tool.",
    momentum: 66.3,
    domains: ["funding", "dev_tools", "startups"],
    key_entities: ["Cursor", "Series C", "coding agents"],
    article_count: 4,
    status: "active",
  },
  {
    id: "nvidia-inference-chip",
    title: "Nvidia's next inference chip leans on memory bandwidth over FLOPs",
    summary:
      "Nvidia detailed an inference-focused accelerator that prioritizes high-bandwidth memory and interconnect over raw compute, targeting the KV-cache pressure that dominates long-context serving costs.",
    so_what:
      "Optimizing the chip for memory bandwidth is a tell: the industry now treats long-context serving, not training throughput, as the binding constraint on unit economics.",
    momentum: 61.0,
    domains: ["hardware", "infra"],
    key_entities: ["Nvidia", "inference", "HBM"],
    article_count: 3,
    status: "active",
  },
  {
    id: "mcp-server-rce",
    title: "Critical RCE disclosed in a widely used MCP server implementation",
    summary:
      "Researchers reported a remote-code-execution flaw in a popular Model Context Protocol server that mishandled tool-argument parsing, allowing crafted payloads to escape into the host process. A patch has shipped.",
    so_what:
      "MCP turns every connected tool into attack surface with the model's privileges — the security review agents need is the one nobody has written yet.",
    momentum: 57.8,
    domains: ["security", "ai_agents"],
    key_entities: ["MCP", "RCE", "tool calling"],
    article_count: 3,
    status: "active",
  },
  {
    id: "pgvector-09-hnsw",
    title: "pgvector 0.9 lands with faster HNSW index builds",
    summary:
      "The pgvector extension shipped a release cutting HNSW index build times and adding iterative scans that keep recall stable under aggressive filtering, easing a long-standing pain point for filtered vector search in Postgres.",
    so_what:
      "Faster filtered scans make 'just use Postgres' viable for a lot more vector workloads, deferring the jump to a dedicated vector database that many teams never actually needed.",
    momentum: 53.9,
    domains: ["infra", "libraries", "python"],
    key_entities: ["pgvector", "Postgres", "HNSW"],
    article_count: 3,
    status: "active",
  },
  {
    id: "retrieval-vs-long-context",
    title: "New study finds retrieval still beats long context on needle tasks",
    summary:
      "A controlled evaluation reported that retrieval-augmented pipelines outperformed raw long-context prompting on multi-fact 'needle in a haystack' tasks past a certain document length, even with frontier models.",
    so_what: null,
    momentum: 42.7,
    domains: ["research", "llms"],
    key_entities: ["RAG", "long context", "evaluation"],
    article_count: 2,
    status: "active",
  },
  {
    id: "uv-default-packaging",
    title: "uv becomes the default Python packaging tool in a major distro",
    summary:
      "A major Linux distribution set uv as the default Python package and project manager in its next release, citing install speed and reproducible lockfiles over the incumbent pip/virtualenv workflow.",
    so_what:
      "Distro-level defaults are how tooling actually wins — this is the moment uv stops being the fast option and becomes the assumed one.",
    momentum: 28.4,
    domains: ["python", "dev_tools", "open_source"],
    key_entities: ["uv", "Astral", "packaging"],
    article_count: 1,
    status: "active",
  },
];

const articlesById: Record<string, ClusterArticleRef[]> = {
  "opus-48-1m-context": [
    {
      id: "a1",
      title: "Introducing Claude Opus 4.8",
      url: "https://www.anthropic.com/news/claude-opus-4-8",
      source: "Anthropic",
      published_at: "2026-07-02T15:00:00Z",
    },
    {
      id: "a2",
      title: "Claude Opus 4.8 pushes context to 1M tokens",
      url: "https://techcrunch.com/2026/07/02/claude-opus-4-8",
      source: "TechCrunch",
      published_at: "2026-07-02T16:20:00Z",
    },
    {
      id: "a3",
      title: "Anthropic's new model leads agentic coding benchmarks",
      url: "https://www.theverge.com/2026/7/2/claude-opus-4-8-coding",
      source: "The Verge",
      published_at: "2026-07-02T17:05:00Z",
    },
    {
      id: "a4",
      title: "Hands-on: 1M context in Claude Code",
      url: "https://news.ycombinator.com/item?id=41000001",
      source: "Hacker News",
      published_at: "2026-07-02T18:40:00Z",
    },
  ],
  "openai-agent-sdk-leak": [
    {
      id: "b1",
      title: "OpenAI SDK commit hints at native agent orchestration",
      url: "https://news.ycombinator.com/item?id=41000002",
      source: "Hacker News",
      published_at: "2026-07-01T09:10:00Z",
    },
    {
      id: "b2",
      title: "What the leaked agents module tells us about OpenAI's roadmap",
      url: "https://venturebeat.com/ai/openai-agents-sdk-leak",
      source: "VentureBeat",
      published_at: "2026-07-01T12:30:00Z",
    },
  ],
  "meta-llama-400b-open": [
    {
      id: "c1",
      title: "Meta releases Llama 400B under a new permissive license",
      url: "https://ai.meta.com/blog/llama-400b",
      source: "Meta AI",
      published_at: "2026-06-30T14:00:00Z",
    },
    {
      id: "c2",
      title: "The Llama license finally drops the MAU clause",
      url: "https://arstechnica.com/ai/2026/06/llama-400b-license",
      source: "Ars Technica",
      published_at: "2026-06-30T15:45:00Z",
    },
  ],
  "cursor-series-c": [
    {
      id: "d1",
      title: "Cursor raises $200M for agentic coding",
      url: "https://techcrunch.com/2026/06/29/cursor-series-c",
      source: "TechCrunch",
      published_at: "2026-06-29T13:00:00Z",
    },
  ],
  "nvidia-inference-chip": [
    {
      id: "e1",
      title: "Nvidia details a bandwidth-first inference accelerator",
      url: "https://www.tomshardware.com/pc-components/nvidia-inference-chip",
      source: "Tom's Hardware",
      published_at: "2026-06-28T10:15:00Z",
    },
  ],
  "mcp-server-rce": [
    {
      id: "f1",
      title: "RCE in a popular MCP server, patch available",
      url: "https://thehackernews.com/2026/06/mcp-server-rce.html",
      source: "The Hacker News",
      published_at: "2026-06-27T08:00:00Z",
    },
  ],
  "pgvector-09-hnsw": [
    {
      id: "g1",
      title: "pgvector 0.9 released",
      url: "https://github.com/pgvector/pgvector/releases/tag/v0.9.0",
      source: "GitHub",
      published_at: "2026-06-26T19:00:00Z",
    },
  ],
  "retrieval-vs-long-context": [
    {
      id: "h1",
      title: "When retrieval beats long context: a controlled study",
      url: "https://arxiv.org/abs/2606.01234",
      source: "arXiv",
      published_at: "2026-06-25T00:00:00Z",
    },
  ],
  "uv-default-packaging": [
    {
      id: "i1",
      title: "Distro sets uv as the default Python package manager",
      url: "https://lwn.net/Articles/uv-default/",
      source: "LWN",
      published_at: "2026-06-24T11:30:00Z",
    },
  ],
};

export const mockClusterPage: ClusterPage = {
  cards,
  total: cards.length,
  limit: 100,
  offset: 0,
};

export const mockDetails: Record<string, ClusterDetail> = Object.fromEntries(
  cards.map((card) => [card.id, { ...card, articles: articlesById[card.id] ?? [] }]),
);

// Mirrors a real recorded run (DECISIONS.md, 2026-08-02): 263 fetched, 185 classified,
// 16 clusters, 23.6 minutes.
export const mockRunPage: RunPage = {
  runs: [
    {
      id: "mock-run-1",
      started_at: "2026-08-02T09:00:00Z",
      completed_at: "2026-08-02T09:23:36Z",
      status: "completed",
      articles_fetched: 263,
      articles_classified: 185,
      clusters_created: 16,
      clusters_updated: 3,
      cost_usd: 1.02,
      tokens_in: 950_000,
      tokens_out: 42_000,
      stage_timings: { fetch: 4.2, classify: 736.4, embed: 8.1, cluster: 0.4, synthesize: 60.2, momentum: 1.9 },
      error_message: null,
    },
  ],
};
