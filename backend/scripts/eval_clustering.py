"""Clustering threshold eval.

Measures cosine separation between same-story and different-story article pairs,
using the exact production embedding path. This is the gate before frontend work:
if the same/different cosine distributions don't separate, the thresholds aren't
defensible and clustering will either merge unrelated stories or fragment real ones.

Run: ``uv run python -m scripts.eval_clustering`` (needs OPENAI_API_KEY).
Edit the labels in ``fixtures/clustering_eval.json`` — that's the human-judgment part.
"""

import asyncio
import json
from pathlib import Path

from app.core.config import settings
from app.models.article import ArticleInput
from app.services.clustering import cosine_similarity
from app.services.embeddings import embed_texts, format_embedding_input

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "clustering_eval.json"


def _stats(name: str, values: list[float]) -> None:
    mean = sum(values) / len(values)
    print(
        f"{name:9} n={len(values):2d}  min={values[0]:.4f}  mean={mean:.4f}  max={values[-1]:.4f}"
    )


async def main() -> None:
    pairs = json.loads(FIXTURE.read_text())
    articles = [ArticleInput.model_validate(pair[side]) for pair in pairs for side in ("a", "b")]
    vectors = await embed_texts([format_embedding_input(article) for article in articles])

    rows: list[tuple[str, float, str, str]] = []
    for index, pair in enumerate(pairs):
        cosine = cosine_similarity(vectors[2 * index], vectors[2 * index + 1])
        rows.append((pair["label"], cosine, pair["a"]["title"], pair["b"]["title"]))

    rows.sort(key=lambda row: (row[0], -row[1]))
    print(f"\n{'label':9} {'cosine':>7}  pair")
    for label, cosine, title_a, title_b in rows:
        print(f"{label:9} {cosine:7.4f}  {title_a[:44]!r} <-> {title_b[:44]!r}")

    same = sorted(cosine for label, cosine, *_ in rows if label == "same")
    diff = sorted(cosine for label, cosine, *_ in rows if label == "different")

    print("\n--- distributions ---")
    _stats("same", same)
    _stats("different", diff)

    gap = same[0] - diff[-1]
    print(f"\nseparation gap (min-same - max-different): {gap:+.4f}")
    if gap > 0:
        print(f"  separable: any threshold in ({diff[-1]:.4f}, {same[0]:.4f}) works")
        print(f"  midpoint suggestion: {(same[0] + diff[-1]) / 2:.4f}")
    else:
        print("  classes OVERLAP; no single threshold separates them — inspect the misses above")

    print("\n--- behavior at configured thresholds ---")
    thresholds = [
        ("CLUSTER_NEW (raw pairs)", settings.cluster_new_similarity_threshold),
        ("CLUSTER_EXISTING (vs centroid)", settings.cluster_existing_similarity_threshold),
    ]
    for name, threshold in thresholds:
        clustered_same = sum(1 for cosine in same if cosine >= threshold)
        clustered_diff = sum(1 for cosine in diff if cosine >= threshold)
        print(
            f"{name} = {threshold}:  "
            f"same clustered {clustered_same}/{len(same)}  |  "
            f"different clustered {clustered_diff}/{len(diff)}"
        )
    print()


if __name__ == "__main__":
    asyncio.run(main())
