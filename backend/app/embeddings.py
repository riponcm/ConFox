"""Text embeddings for semantic search, from the OpenAI embeddings API.

Without OPENAI_API_KEY nothing is embedded: the loader indexes documents without vectors and search runs keyword
only. Every batch is one `embed` span and records its token count and cost.
"""

import logging
from functools import cache

from elasticsearch import NotFoundError
from openai import OpenAI
from opentelemetry import metrics, trace

from .config import settings
from .es import es

log = logging.getLogger(__name__)
tracer = trace.get_tracer("confox.embeddings")
meter = metrics.get_meter("confox.embeddings")

TOKENS = meter.create_counter("confox.embeddings.tokens", unit="{token}", description="Tokens sent to embed")
COST = meter.create_counter("confox.embeddings.cost", unit="USD", description="Estimated embedding cost")

BATCH = 100
# US dollars per million input tokens (OpenAI list prices).
PRICE_PER_MTOK = {"text-embedding-3-small": 0.02, "text-embedding-3-large": 0.13}


def enabled() -> bool:
    return bool(settings.openai_api_key.strip())


@cache
def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key.strip())


def cost_usd(model: str, tokens: int) -> float:
    return tokens * PRICE_PER_MTOK.get(model, 0.0) / 1_000_000


def embed(texts: list[str]) -> list[list[float]]:
    """One vector per text, in order. Returns [] when embeddings are disabled (no key)."""
    if not enabled() or not texts:
        return []
    model = settings.embed_model
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        batch = [t.strip() or " " for t in texts[start : start + BATCH]]  # the API rejects empty strings
        with tracer.start_as_current_span("embed") as span:
            span.set_attribute("gen_ai.operation.name", "embeddings")
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("confox.embed.count", len(batch))
            resp = _client().embeddings.create(model=model, input=batch, dimensions=settings.embed_dims)
            tokens = resp.usage.total_tokens
            cost = cost_usd(model, tokens)
            span.set_attribute("gen_ai.usage.input_tokens", tokens)
            span.set_attribute("confox.cost_usd", cost)
            TOKENS.add(tokens, {"model": model})
            COST.add(cost, {"model": model})
        vectors.extend(d.embedding for d in sorted(resp.data, key=lambda d: d.index))
    return vectors


def get_vector(index: str, doc_id: str) -> list[float] | None:
    """The stored embedding of one document, or None when the document or its vector is missing.

    Elasticsearch 9 leaves dense vectors out of `_source` by default, so they must be asked for explicitly.
    """
    try:
        doc = es.get(index=index, id=doc_id, source_includes=["embedding"], source_exclude_vectors=False)
    except NotFoundError:
        return None
    return (doc.get("_source") or {}).get("embedding")
