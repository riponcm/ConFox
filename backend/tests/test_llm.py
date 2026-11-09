import asyncio

import pytest

from app import llm


def test_cost_uses_the_price_table():
    # 1M input at $4 + 1M output at $20 for Claude Opus 5.5
    assert llm.cost_usd("claude-opus-5-5", 1_000_000, 1_000_000) == 24.0
    assert llm.cost_usd("claude-opus-5-5", 1000, 200) == 0.008
    assert llm.cost_usd("unknown-model", 1000, 200) == 0.0


def test_complete_traces_a_chat_span_with_usage(fake_claude, spans):
    fake = fake_claude(["Hello ", "Emma"])
    text, usage = llm.complete("system", [{"role": "user", "content": "hi"}], feature="test")
    assert text == "Hello Emma"
    assert usage.cost_usd == 0.008

    span = next(s for s in spans.get_finished_spans() if s.name == "chat claude-opus-5-5")
    a = span.attributes
    assert a["gen_ai.operation.name"] == "chat"
    assert a["gen_ai.provider.name"] == "anthropic"
    assert a["gen_ai.request.model"] == "claude-opus-5-5"
    assert a["gen_ai.response.model"] == "claude-opus-5-5"
    assert a["gen_ai.usage.input_tokens"] == 1000
    assert a["gen_ai.usage.output_tokens"] == 200
    assert a["confox.llm.cost_usd"] == 0.008

    req = fake.calls[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["fallbacks"] == "default" and llm.FALLBACK_BETA in req["betas"]
    assert "temperature" not in req and "thinking" not in req


def test_complete_raises_on_refusal(fake_claude):
    fake_claude(["partial"], stop_reason="refusal")
    with pytest.raises(llm.Refused):
        llm.complete("system", [{"role": "user", "content": "hi"}], feature="test")


def test_stream_yields_text_then_usage(fake_claude, spans):
    fake_claude(["a", "b"])

    async def collect():
        return [x async for x in llm.stream("s", [{"role": "user", "content": "q"}], feature="test")]

    items = asyncio.run(collect())
    assert items[:2] == ["a", "b"]
    assert isinstance(items[2], llm.Usage) and items[2].output_tokens == 200
    assert any(s.name == "chat claude-opus-5-5" for s in spans.get_finished_spans())
