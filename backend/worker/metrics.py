"""Per-run cost and latency accounting (plan-day-deploy-and-measure.md H6-H7).

The pipeline could not previously state what a run costs — `DECISIONS.md` carried an
estimate (~$0.004/article) with no instrumentation behind it. This module times each
pipeline stage and accumulates PydanticAI's per-call `RunUsage` into one running total
per model, then prices the totals off a static table. Nothing here reads or writes the
database; the caller persists `RunMetrics.cost_usd()` / `.tokens_in` / `.tokens_out` /
`.stage_timings`.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from pydantic_ai.usage import RunUsage


@dataclass(frozen=True)
class _ModelPrice:
    input_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float
    output_per_mtok: float


# USD per 1M tokens — Anthropic list pricing, matched by model family rather than exact
# version string: config.py's default (claude-sonnet-4-6) and .env's configured value
# (claude-sonnet-5) already disagree, and pinning to one literal would silently stop
# pricing the moment either changes again. Cache reads bill at 0.1x the input rate,
# writes (5-minute TTL) at 1.25x. Nothing in this codebase sets cache_control yet, so
# cache_write/read are expected to be 0 today — confirming that is part of what this
# instrumentation is for (DECISIONS.md's prompt-caching question).
_HAIKU_PRICE = _ModelPrice(
    input_per_mtok=1.00, cache_write_per_mtok=1.25, cache_read_per_mtok=0.10, output_per_mtok=5.00
)
_SONNET_PRICE = _ModelPrice(
    input_per_mtok=3.00, cache_write_per_mtok=3.75, cache_read_per_mtok=0.30, output_per_mtok=15.00
)
_EMBEDDING_PRICE_PER_MTOK = 0.02  # text-embedding-3-small


class UnpricedModelError(RuntimeError):
    pass


def _model_price(model_name: str) -> _ModelPrice:
    name = model_name.removeprefix("anthropic:").lower()
    if "haiku" in name:
        return _HAIKU_PRICE
    if "sonnet" in name:
        return _SONNET_PRICE
    raise UnpricedModelError(f"No price entry for model family in {model_name!r}")


def _usage_cost(usage: RunUsage, price: _ModelPrice) -> float:
    return (
        usage.input_tokens * price.input_per_mtok
        + usage.cache_write_tokens * price.cache_write_per_mtok
        + usage.cache_read_tokens * price.cache_read_per_mtok
        + usage.output_tokens * price.output_per_mtok
    ) / 1_000_000


@dataclass
class RunMetrics:
    classifier_model: str
    synthesis_model: str
    classifier_usage: RunUsage = field(default_factory=RunUsage)
    synthesis_usage: RunUsage = field(default_factory=RunUsage)
    # Embedding tokens are estimated (chars/4), not read from the API response — embedding
    # cost is a rounding error next to the two LLM stages, so exactness here isn't worth
    # threading a return-type change through embed_texts's other callers (eval scripts).
    embedding_tokens: int = 0
    stage_timings: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def timed_stage(self, name: str) -> Iterator[None]:
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - start
            self.stage_timings[name] = self.stage_timings.get(name, 0.0) + elapsed

    @property
    def tokens_in(self) -> int:
        return self.classifier_usage.input_tokens + self.synthesis_usage.input_tokens

    @property
    def tokens_out(self) -> int:
        return self.classifier_usage.output_tokens + self.synthesis_usage.output_tokens

    def cost_usd(self) -> float:
        return (
            _usage_cost(self.classifier_usage, _model_price(self.classifier_model))
            + _usage_cost(self.synthesis_usage, _model_price(self.synthesis_model))
            + self.embedding_tokens / 1_000_000 * _EMBEDDING_PRICE_PER_MTOK
        )
