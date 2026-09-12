import logging

from openai import AsyncOpenAI
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models import ArticleInput

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


class EmbeddingConfigError(RuntimeError):
    pass


def build_embedding_client() -> AsyncOpenAI:
    api_key = settings.openai_api_key_value
    if api_key is None:
        raise EmbeddingConfigError("OPENAI_API_KEY is required for embeddings")
    return AsyncOpenAI(api_key=api_key)


def get_embedding_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = build_embedding_client()
    return _client


# A missing key is deterministic: retrying it three times wastes attempts and buries the
# real message inside RetryError[...], which is how a missing OPENAI_API_KEY in CI read as
# a tenacity failure two tracebacks deep. Retry transport errors, never configuration.
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_not_exception_type(EmbeddingConfigError),
)
async def _embed_batch(texts: list[str]) -> list[list[float]]:
    response = await get_embedding_client().embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
    )
    # Response items carry an index; sort to guarantee input order is preserved.
    ordered = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts in input order. Caller owns how an article becomes a string."""
    if not texts:
        return []
    # OpenAI accepts large input arrays; batch to stay well under request limits.
    batch_size = settings.embedding_batch_size
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(await _embed_batch(texts[start : start + batch_size]))
    return vectors


def format_embedding_input(article: ArticleInput) -> str:
    parts = [article.title]
    if article.content:
        content = " ".join(article.content.split())
        parts.append(content[: settings.embedding_max_content_chars])
    tags = article.source_metadata.get("tags", [])
    if tags:
        parts.append(", ".join(tags))
    return "\n".join(parts)
