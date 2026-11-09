"""Every Claude call goes through here, so each one is traced, counted and priced the same way.

One span per call, named `chat {model}`, with the OpenTelemetry GenAI semantic-convention attributes plus
`confox.llm.cost_usd`. The Anthropic SDK adds its own `anthropic.messages.create` span as a child. Metrics:
`confox.llm.tokens` (by type and model), `confox.llm.cost_usd` and `confox.llm.duration` (ms).

Streaming calls record usage when the stream ends, from the final message.
"""

import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass

import anthropic
from opentelemetry import metrics, trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from .config import settings

log = logging.getLogger(__name__)
tracer = trace.get_tracer("confox.llm")
meter = metrics.get_meter("confox.llm")

TOKENS = meter.create_counter("confox.llm.tokens", unit="{token}", description="Claude tokens by type and model")
COST = meter.create_counter("confox.llm.cost_usd", unit="USD", description="Estimated Claude cost")
DURATION = meter.create_histogram("confox.llm.duration", unit="ms", description="Claude call duration")
CHAT_REQUESTS = meter.create_counter("confox.chat.requests", unit="{request}", description="Ask and Catch up turns")

# US dollars per million tokens. Source: the claude-api skill's model table (cached 2026-10-06) and
# shared/prompt-caching.md: Claude Opus 5.5 is $4 input / $20 output, cache reads $0.20, and 5-minute cache writes
# cost 1.25x the input price. Claude Opus 5 ($5 / $25) and Opus 4.8 ($5 / $25) are listed because the server-side
# fallback may answer with them. Unknown models cost 0 so a missing row never breaks a request.
PRICES: dict[str, dict[str, float]] = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25},
}

# Opus 5.5 classifiers can decline a request; "default" re-runs a decline on Anthropic's recommended model.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class Refused(RuntimeError):
    """Claude (and its fallback) declined the request: stop_reason "refusal"."""


@dataclass
class Usage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    stop_reason: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float:
    p = PRICES.get(model)
    if not p:
        return 0.0
    total = (
        input_tokens * p["input"]
        + output_tokens * p["output"]
        + cache_read * p["cache_read"]
        + cache_write * p["cache_write"]
    )
    return round(total / 1_000_000, 6)


_sync: anthropic.Anthropic | None = None
_async: anthropic.AsyncAnthropic | None = None


def _key() -> str | None:
    return settings.anthropic_api_key or None


def sync_client() -> anthropic.Anthropic:
    global _sync
    if _sync is None:
        _sync = anthropic.Anthropic(api_key=_key())
    return _sync


def async_client() -> anthropic.AsyncAnthropic:
    global _async
    if _async is None:
        _async = anthropic.AsyncAnthropic(api_key=_key())
    return _async


def _request(system: str, messages: list[dict], max_tokens: int, effort: str, output_format: dict | None) -> dict:
    output_config: dict = {"effort": effort}
    if output_format:
        output_config["format"] = output_format
    return {
        "model": settings.llm_model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "output_config": output_config,
        "betas": [FALLBACK_BETA],
        "fallbacks": "default",
    }


def _start_span(feature: str, max_tokens: int):
    model = settings.llm_model
    return tracer.start_as_current_span(
        f"chat {model}",
        kind=SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": "anthropic",
            "gen_ai.request.model": model,
            "gen_ai.request.max_tokens": max_tokens,
            "confox.llm.feature": feature,
        },
    )


def _record(span, final, feature: str, started: float) -> Usage:
    """Put usage and cost on the span and the metrics. `final` is the SDK's final message."""
    u = final.usage
    model = final.model or settings.llm_model
    cache_read = u.cache_read_input_tokens or 0
    cache_write = u.cache_creation_input_tokens or 0
    usage = Usage(
        model=model,
        input_tokens=u.input_tokens or 0,
        output_tokens=u.output_tokens or 0,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
        stop_reason=final.stop_reason,
    )
    # Top-level usage covers the attempt that produced the message; enough for a demo-scale cost estimate.
    usage.cost_usd = cost_usd(model, usage.input_tokens, usage.output_tokens, cache_read, cache_write)

    span.set_attribute("gen_ai.response.model", model)
    span.set_attribute("gen_ai.response.id", final.id or "")
    span.set_attribute("gen_ai.response.finish_reasons", [final.stop_reason or ""])
    span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
    if cache_read:
        span.set_attribute("gen_ai.usage.cache_read.input_tokens", cache_read)
    if cache_write:
        span.set_attribute("gen_ai.usage.cache_creation.input_tokens", cache_write)
    span.set_attribute("confox.llm.cost_usd", usage.cost_usd)

    attrs = {"model": model, "feature": feature}
    for kind, n in (
        ("input", usage.input_tokens),
        ("output", usage.output_tokens),
        ("cache_read", cache_read),
        ("cache_write", cache_write),
    ):
        if n or kind in ("input", "output"):
            TOKENS.add(n, {**attrs, "type": kind})
    COST.add(usage.cost_usd, attrs)
    DURATION.record(usage.duration_ms, attrs)
    if final.stop_reason == "refusal":
        log.warning("Claude declined the %s request (stop_reason=refusal)", feature)
    return usage


def _fail(span, exc: Exception, feature: str, started: float) -> None:
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
    span.set_attribute("error.type", type(exc).__name__)
    DURATION.record(
        round((time.perf_counter() - started) * 1000, 1),
        {"model": settings.llm_model, "feature": feature, "error.type": type(exc).__name__},
    )
    log.error("Claude call for %s failed: %s", feature, exc)


def text_of(final) -> str:
    return "".join(b.text for b in final.content if b.type == "text")


def complete(
    system: str,
    messages: list[dict],
    *,
    feature: str,
    max_tokens: int = 4096,
    effort: str = "low",
    output_format: dict | None = None,
) -> tuple[str, Usage]:
    """One Claude call, streamed under the hood (no HTTP timeouts on long output), returning the full text."""
    started = time.perf_counter()
    with _start_span(feature, max_tokens) as span:
        try:
            req = _request(system, messages, max_tokens, effort, output_format)
            with sync_client().beta.messages.stream(**req) as stream:
                final = stream.get_final_message()
        except Exception as exc:
            _fail(span, exc, feature, started)
            raise
        usage = _record(span, final, feature, started)
        if final.stop_reason == "refusal":
            raise Refused(f"Claude declined the {feature} request")
        return text_of(final), usage


async def stream(
    system: str,
    messages: list[dict],
    *,
    feature: str,
    max_tokens: int = 4096,
    effort: str = "low",
) -> AsyncIterator[str | Usage]:
    """Yield text chunks as Claude writes them, then one final `Usage`.

    An async generator, so Starlette iterates it in the request's own task and the span context stays valid
    across yields. Errors are recorded on the span and re-raised for the caller to report.
    """
    started = time.perf_counter()
    with _start_span(feature, max_tokens) as span:
        try:
            req = _request(system, messages, max_tokens, effort, None)
            async with async_client().beta.messages.stream(**req) as s:
                async for event in s:
                    if event.type == "text":
                        yield event.text
                final = await s.get_final_message()
        except Exception as exc:
            _fail(span, exc, feature, started)
            raise
        yield _record(span, final, feature, started)


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


async def sse_answer(
    sources: list[dict], system: str, messages: list[dict], *, feature: str, max_tokens: int = 2048
) -> AsyncIterator[str]:
    """The Server-Sent Events both chat endpoints send: `sources`, then `delta` chunks, then `done` (or `error`)."""
    CHAT_REQUESTS.add(1, {"feature": feature})
    yield sse({"type": "sources", "sources": sources})
    try:
        async for item in stream(system, messages, feature=feature, max_tokens=max_tokens):
            if isinstance(item, Usage):
                yield sse({"type": "done", "usage": item.as_dict()})
            else:
                yield sse({"type": "delta", "text": item})
    except Exception as exc:  # already logged and recorded on the span by stream()
        yield sse({"type": "error", "message": f"The answer failed ({type(exc).__name__}). Please try again."})
