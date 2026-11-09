"""Shared test fixtures. Tests never call the Claude API: every test gets a fake client."""

from types import SimpleNamespace

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import llm
from app.main import app  # noqa: F401  (installs the tracer provider before spans are recorded)

_exporter = InMemorySpanExporter()
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(_exporter))


def _final(text: str, model: str = "claude-opus-5-5", stop_reason: str = "end_turn"):
    return SimpleNamespace(
        id="msg_test",
        model=model,
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(
            input_tokens=1000, output_tokens=200, cache_read_input_tokens=None, cache_creation_input_tokens=None
        ),
    )


class FakeClaude:
    """Stands in for both Anthropic clients. `chunks` is what Claude 'writes'; `calls` records each request."""

    def __init__(self, chunks: list[str], stop_reason: str = "end_turn"):
        self.chunks = chunks
        self.stop_reason = stop_reason
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        return _Stream(self.chunks, _final("".join(self.chunks), stop_reason=self.stop_reason))


class _Stream:
    def __init__(self, chunks, final):
        self.chunks, self.final = chunks, final

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.final

    @property
    def current_message_snapshot(self):  # what the SDK has accumulated so far
        return self.final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def __aiter__(self):
        for c in self.chunks:
            yield SimpleNamespace(type="text", text=c)


class _AsyncFinal(_Stream):
    async def get_final_message(self):  # the async stream's helper is awaited
        return self.final


def _async_stream(fake: FakeClaude):
    def stream(**kwargs):
        fake.calls.append(kwargs)
        return _AsyncFinal(fake.chunks, _final("".join(fake.chunks), stop_reason=fake.stop_reason))

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))


class _NoClaude:
    @property
    def beta(self):
        raise AssertionError("tests must not call the Claude API; use the fake_claude fixture")


@pytest.fixture(autouse=True)
def no_real_claude(monkeypatch):
    monkeypatch.setattr(llm, "_sync", _NoClaude())
    monkeypatch.setattr(llm, "_async", _NoClaude())


@pytest.fixture
def fake_claude(monkeypatch):
    def install(chunks: list[str], stop_reason: str = "end_turn") -> FakeClaude:
        fake = FakeClaude(chunks, stop_reason)
        monkeypatch.setattr(llm, "_sync", fake)
        monkeypatch.setattr(llm, "_async", _async_stream(fake))
        return fake

    return install


@pytest.fixture
def spans():
    _exporter.clear()
    yield _exporter
    _exporter.clear()
