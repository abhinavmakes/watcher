import pytest
from pydantic_ai.usage import RunUsage

from worker.metrics import RunMetrics


def test_run_metrics_cost_usd_matches_hand_computed_price() -> None:
    metrics = RunMetrics(
        classifier_model="anthropic:claude-haiku-4-5-20251001",
        synthesis_model="anthropic:claude-sonnet-5",
    )
    metrics.classifier_usage.incr(RunUsage(input_tokens=1_000_000, output_tokens=1_000_000))
    metrics.synthesis_usage.incr(
        RunUsage(input_tokens=1_000_000, cache_read_tokens=200_000, output_tokens=500_000)
    )
    metrics.embedding_tokens = 1_000_000

    # Haiku ($1 in / $5 out):    1*1.00 + 1*5.00        = 6.00
    # Sonnet ($3 in / $15 out,
    #   cache read at 0.1x):     1*3.00 + 0.2*0.30 + 0.5*15.00 = 10.56
    # Embeddings ($0.02/MTok):   1*0.02                 = 0.02
    expected = 6.00 + 10.56 + 0.02
    assert metrics.cost_usd() == pytest.approx(expected)
    assert metrics.tokens_in == 2_000_000
    assert metrics.tokens_out == 1_500_000
