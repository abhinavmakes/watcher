import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from app.agents.classifier import classify_article
from app.core.config import settings
from app.models.classification import ClassificationOutput
from app.models.classifier_eval import LabeledArticle, RelevanceBand

logger = logging.getLogger(__name__)

DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "classifier_eval.json"

NOISE_PRECISION_TARGET = 0.90
NOISE_RECALL_TARGET = 0.75
DOMAIN_ACCURACY_TARGET = 0.70


def _band_for_score(score: float) -> RelevanceBand:
    if score < 0.35:
        return RelevanceBand.LOW
    if score < 0.70:
        return RelevanceBand.MID
    return RelevanceBand.HIGH


def _load_fixture(path: Path) -> list[LabeledArticle]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [LabeledArticle.model_validate(item) for item in data]


async def _classify_all(items: list[LabeledArticle]) -> list[ClassificationOutput]:
    interval = 60 / settings.classifier_rpm
    predictions: list[ClassificationOutput] = []
    for i, item in enumerate(items):
        if i > 0:
            await asyncio.sleep(interval)
        print(f"  classifying {i + 1}/{len(items)}: {item.article.title[:60]}", flush=True)
        predictions.append(await classify_article(item.article))
    return predictions


@dataclass
class NoiseMetrics:
    # noise is the positive class
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else float("nan")

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else float("nan")

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else float("nan")


@dataclass
class EvalResult:
    noise: NoiseMetrics
    domain_hits: int
    domain_total: int
    band_hits: int
    band_total: int


def _evaluate(items: list[LabeledArticle], predictions: list[ClassificationOutput]) -> EvalResult:
    noise = NoiseMetrics()
    domain_hits = domain_total = 0
    band_hits = band_total = 0

    print("\n--- disagreements ---")
    for item, pred in zip(items, predictions, strict=True):
        expected_noise = item.expected_is_noise
        assert expected_noise is not None  # unlabeled rows filtered before this call
        title = item.article.title

        if expected_noise and pred.is_noise:
            noise.tp += 1
        elif not expected_noise and pred.is_noise:
            noise.fp += 1
            print(f"[FALSE-NOISE]  {title!r} -> pred noise (score {pred.relevance_score})")
        elif not expected_noise and not pred.is_noise:
            noise.tn += 1
        else:  # expected noise, predicted signal
            noise.fn += 1
            print(f"[MISSED-NOISE] {title!r} -> pred signal (score {pred.relevance_score})")

        if not expected_noise and item.expected_domains:
            domain_total += 1
            expected = set(item.expected_domains)
            predicted = set(pred.domains)
            if expected & predicted:
                domain_hits += 1
            else:
                got = [d.value for d in pred.domains]
                want = [d.value for d in item.expected_domains]
                print(f"[DOMAIN-MISS]  {title!r} -> want any of {want}, got {got}")

        if item.relevance_band is not None:
            band_total += 1
            if _band_for_score(pred.relevance_score) == item.relevance_band:
                band_hits += 1

    return EvalResult(noise, domain_hits, domain_total, band_hits, band_total)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="Run the classifier over a labeled fixture.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE_PATH)
    args = parser.parse_args()

    all_items = _load_fixture(args.fixture)
    items = [item for item in all_items if item.is_labeled]
    unlabeled = len(all_items) - len(items)
    if not items:
        raise RuntimeError(f"No labeled rows in {args.fixture}; set expected_is_noise first")
    if unlabeled:
        logger.warning("skipping %d unlabeled rows", unlabeled)

    predictions = asyncio.run(_classify_all(items))
    result = _evaluate(items, predictions)
    noise = result.noise

    domain_accuracy = result.domain_hits / result.domain_total if result.domain_total else None
    band_accuracy = result.band_hits / result.band_total if result.band_total else None

    print("\n=== classifier eval ===")
    print(f"labeled: {len(items)}  (noise={noise.tp + noise.fn}, signal={noise.fp + noise.tn})")
    print(f"noise precision: {noise.precision:.2f}  (target >= {NOISE_PRECISION_TARGET})")
    print(f"noise recall:    {noise.recall:.2f}  (target >= {NOISE_RECALL_TARGET})")
    print(f"noise F1:        {noise.f1:.2f}")
    print(f"  confusion: tp={noise.tp} fp={noise.fp} tn={noise.tn} fn={noise.fn}")
    if domain_accuracy is not None:
        print(f"domain accuracy: {domain_accuracy:.2f}  (target >= {DOMAIN_ACCURACY_TARGET})")
    if band_accuracy is not None:
        print(f"relevance-band accuracy: {band_accuracy:.2f}")

    passed = noise.precision >= NOISE_PRECISION_TARGET and noise.recall >= NOISE_RECALL_TARGET
    if domain_accuracy is not None:
        passed = passed and domain_accuracy >= DOMAIN_ACCURACY_TARGET

    print(f"\nRESULT: {'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
