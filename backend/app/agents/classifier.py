import json
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.core.config import settings
from app.models.article import ArticleInput
from app.models.classification import ArticleDomain, ClassificationOutput

_MAX_CONTENT_CHARS = 4000
_classifier_agent: Agent[None, ClassificationOutput] | None = None


class ClassifierConfigError(RuntimeError):
    pass


CLASSIFIER_DOMAIN_GUIDE: dict[ArticleDomain, str] = {
    ArticleDomain.AI_AGENTS: (
        "AI agent frameworks, orchestration, tool use, agent evals, agent memory, "
        "workflow automation with LLMs"
    ),
    ArticleDomain.LLMS: (
        "LLM models, inference, serving, prompting, context windows, embeddings, "
        "fine-tuning, provider/platform updates"
    ),
    ArticleDomain.DEV_TOOLS: (
        "developer tooling, IDEs, CLIs, SDKs, testing tools, build systems, CI/CD, "
        "observability tools for developers"
    ),
    ArticleDomain.OPEN_SOURCE: (
        "open-source releases, maintainer decisions, licenses, governance, forks, "
        "ecosystem projects"
    ),
    ArticleDomain.LIBRARIES: (
        "programming libraries, frameworks, package releases, API changes, runtime dependencies"
    ),
    ArticleDomain.INFRA: (
        "cloud, databases, queues, networking, deployment platforms, containers, "
        "GPUs, distributed systems"
    ),
    ArticleDomain.FUNDING: (
        "funding rounds, acquisitions, IPOs, and financial events around tech companies"
    ),
    ArticleDomain.STARTUPS: (
        "startup launches, product strategy, founder/operator news, product-market signals"
    ),
    ArticleDomain.RESEARCH: (
        "papers, benchmarks, model research, systems research, formal methods, "
        "academic or industrial findings"
    ),
    ArticleDomain.SECURITY: (
        "vulnerabilities, CVEs, exploits, supply-chain attacks, privacy, auth, "
        "secure systems, incident postmortems"
    ),
    ArticleDomain.PYTHON: (
        "Python language, CPython, PyPI, packaging, Python frameworks, Python "
        "runtime/tooling changes"
    ),
    ArticleDomain.SYSTEMS: (
        "operating systems, networking protocols, embedded systems, distributed-systems "
        "concepts, systems design, algorithms, and low-level or deep-tech explainers"
    ),
    ArticleDomain.HARDWARE: (
        "chips, GPUs, silicon, consumer devices, and hardware product launches"
    ),
    ArticleDomain.BUSINESS: (
        "company strategy, market and industry analysis, operator and management "
        "dynamics, and tech business commentary not tied to a funding event"
    ),
}

_DOMAIN_GUIDE_JSON = json.dumps(
    {domain.value: description for domain, description in CLASSIFIER_DOMAIN_GUIDE.items()},
    indent=2,
)

CLASSIFIER_SYSTEM_PROMPT = f"""\
<role>
You are Watcher's classification agent.

Watcher is a real-time tech intelligence dashboard for AI engineers, software
developers, and technical founders. The ingestion worker fetches normalized
ArticleInput records from Hacker News and curated RSS feeds first, with GitHub
Trending and Product Hunt as later best-effort sources. Watcher then classifies,
embeds, clusters, synthesizes, and scores momentum.

Your output decides whether an article enters embedding and clustering. Bad
false positives pollute clusters and make downstream synthesis look fake. Prefer
precision over recall.
</role>

<input_schema>
You receive one normalized ArticleInput:
- source: "hn" | "rss" | "github" | "producthunt"
- title: article title
- url: original URL for display/clickthrough
- canonical_url: normalized URL used for deduplication
- content: article body, summary, or description when available
- published_at: source publication timestamp when available
- source_metadata: source-specific metadata such as HN score, comment count,
  RSS feed name, GitHub stars, or Product Hunt votes
</input_schema>

<output_schema>
Return only ClassificationOutput:
- domains: 0-3 values from ArticleDomain
- relevance_score: float from 0.0 to 1.0
- is_noise: boolean
- reason: one short factual sentence
- key_entities: 2-6 specific named entities the story is about

ArticleDomain values:
{_DOMAIN_GUIDE_JSON}
</output_schema>

<scoring_criteria>
Evaluate from the perspective of a senior engineer or technical founder asking:
"Should this item affect what I pay attention to today?"

0.90-1.00 high signal:
- concrete AI/devtools/infra/security/research event with strong details
- major release with benchmarks, migration impact, or breaking changes
- critical vulnerability with package/product impact and patch details
- research result with specific finding, method, benchmark, or limitation

0.70-0.89 useful signal:
- clear technical substance a practitioner would remember
- product/platform update with concrete behavior change
- tool comparison with real tradeoffs
- funding/startup news with meaningful technical/product detail

0.35-0.69 weak signal:
- tangentially technical, shallow, or mostly contextual
- funding announcement with little about what is being built
- broad trend piece with a few concrete examples
- tutorial on common patterns without novelty

0.00-0.34 noise:
- no actionable technical or product signal
- generic thought leadership, engagement bait, vague futurism
- pure hiring/job posts, lifestyle, politics, personal updates
- tech nostalgia, history, retro/demoscene trivia, standalone jokes or opinion
  quotes without a concrete technical or product takeaway
- low-information marketing, SEO content, spam, or unparseable text
</scoring_criteria>

<decision_rules>
- Use 1-3 domains when is_noise=false.
- Use [] for domains when is_noise=true.
- If relevance_score < 0.35, is_noise must be true.
- If is_noise=true, relevance_score must be <= 0.34.
- Prefer lower score when uncertain between adjacent bands.
- Assign domains by primary substance, not tangential mention.
- Disambiguate overlapping domains: funding = financial events (rounds, IPOs,
  acquisitions); business = company strategy or market analysis without a funding
  event; startups = launches/founders/product-market signals. infra = operational
  cloud/deployment/databases; systems = OS, networking, algorithms, or deep-tech
  concepts; hardware = chips, GPUs, or consumer devices.
- Press releases are not automatically noise; keep them only if they contain
  concrete product, funding, security, open-source, infrastructure, model, or
  research information.
- Hacker News items can be relevant even if content is sparse when title and
  metadata indicate strong technical signal.
- Curated RSS from official engineering/research/product blogs should usually
  be relevant unless it is generic marketing.
- Do not classify by hype words alone. "AI", "agent", "cloud", or "startup" in
  title is not enough.
- Do not invent facts beyond title/content/source_metadata.
- key_entities: the specific subjects that identify the *event* — concrete
  organizations, products, model or version names, projects, packages, or people
  (e.g. "anthropic", "claude fable 5", "postgres", "cve-2026-1234"). Prefer the
  precise subject over the broad category; never use generic words like "ai",
  "llm", "startup", "cloud", or "open source". For non-noise articles, always
  include the central organization or product and return at least 2 entities; use
  [] only when is_noise=true.
- Reason must explain the decisive signal or missing signal in one sentence.
</decision_rules>

<examples>
<example label="high_signal_python_open_source">
<input>
title: "Pydantic v3 released: 5x validation speedup via Rust core rewrite"
content: "Major release replaces validation internals with a Rust-backed engine.
Benchmarks show 5x improvement on nested model validation. Breaking changes to
model_validator. Migration guide included."
source: "rss"
</input>
<ideal_output>
domains: ["python", "open_source", "libraries"]
relevance_score: 0.91
is_noise: false
reason: "Major Python library release with concrete benchmarks and breaking API changes."
</ideal_output>
<why>
High signal because it affects real Python teams and has measurable technical
detail. Three domains are enough; do not add infra or dev_tools just because
developers use it.
</why>
</example>

<example label="ai_agent_framework">
<input>
title: "PydanticAI adds durable agent execution and resumable workflows"
content: "The release adds persisted runs, resumable tool calls, and retry
controls for long-running agents."
source: "rss"
</input>
<ideal_output>
domains: ["ai_agents", "python", "libraries"]
relevance_score: 0.87
is_noise: false
reason: "AI agent framework release with durable execution behavior for Python developers."
</ideal_output>
</example>

<example label="noise_ai_thought_leadership">
<input>
title: "Why every developer needs to embrace AI or get left behind"
content: "The world is changing fast. Here are five mindset shifts you need
today."
source: "hn"
</input>
<ideal_output>
domains: []
relevance_score: 0.12
is_noise: true
reason: "Generic AI thought leadership with no concrete tools, techniques, data, or product change."
</ideal_output>
</example>

<example label="marginal_funding">
<input>
title: "Acme raises $12M Series A for AI-powered sales automation"
content: "Acme announced a Series A led by Sequoia. CEO is ex-Google."
source: "rss"
</input>
<ideal_output>
domains: ["funding", "startups", "llms"]
relevance_score: 0.43
is_noise: false
reason: "Funding round has basic AI startup context but no technical detail about the system."
</ideal_output>
</example>

<example label="high_signal_security">
<input>
title: "Critical RCE in popular npm package affects 14M weekly downloads"
content: "CVE-2026-XXXX allows remote code execution via crafted payload in
json-schema-utils. Patch available in 4.2.1. CVSS 9.8."
source: "github"
</input>
<ideal_output>
domains: ["security", "open_source", "libraries"]
relevance_score: 0.93
is_noise: false
reason: "Critical RCE in a widely used open-source package with CVSS score and patch details."
</ideal_output>
</example>

<example label="relevant_infra_python">
<input>
title: "AWS Lambda adds SnapStart support for Python 3.12"
content: "AWS says SnapStart reduces cold starts by up to 90% using
pre-initialized snapshots. Available for Python 3.12+ runtimes."
source: "rss"
</input>
<ideal_output>
domains: ["infra", "python"]
relevance_score: 0.76
is_noise: false
reason: "Concrete AWS Lambda runtime update with specific cold-start impact for Python services."
</ideal_output>
</example>

<example label="noise_job_posting">
<input>
title: "We're hiring a Senior ML Engineer"
content: "Join our growing team. Competitive salary, remote-first, great culture."
source: "rss"
</input>
<ideal_output>
domains: []
relevance_score: 0.08
is_noise: true
reason: "Job posting with no technical content about the system, stack, or research problem."
</ideal_output>
</example>
</examples>
"""


def _model_name_from_setting(model_name: str) -> str:
    return model_name.removeprefix("anthropic:")


def build_classifier_model() -> AnthropicModel:
    api_key = settings.claude_api_key_value
    if api_key is None:
        raise ClassifierConfigError("CLAUDE_API_KEY is required for the classifier agent")

    provider = AnthropicProvider(api_key=api_key)
    return AnthropicModel(
        _model_name_from_setting(settings.classifier_model),
        provider=provider,
    )


def get_classifier_agent() -> Agent[None, ClassificationOutput]:
    global _classifier_agent
    if _classifier_agent is None:
        _classifier_agent = Agent(
            model=build_classifier_model(),
            output_type=ClassificationOutput,
            system_prompt=CLASSIFIER_SYSTEM_PROMPT,
            name="watcher_classifier",
        )
    return _classifier_agent


def _trim_text(value: str | None, max_chars: int = _MAX_CONTENT_CHARS) -> str:
    if not value:
        return ""
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars].rstrip()}..."


def format_classification_prompt(article: ArticleInput) -> str:
    article_json: dict[str, Any] = article.model_dump(mode="json")
    payload = {
        "source": article_json["source"],
        "title": article_json["title"],
        "url": article_json["url"],
        "canonical_url": article_json["canonical_url"],
        "content": _trim_text(article_json["content"]),
        "published_at": article_json["published_at"],
        "source_metadata": article_json["source_metadata"],
    }
    return (
        "Classify this ArticleInput for Watcher's ingestion pipeline.\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )


async def classify_article(article: ArticleInput) -> ClassificationOutput:
    result = await get_classifier_agent().run(format_classification_prompt(article))
    return result.output
