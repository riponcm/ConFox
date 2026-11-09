"""OpenTelemetry for the API: traces, metrics and logs over OTLP/HTTP (Dash0 in our setup).

Exporters are only installed when OTEL_EXPORTER_OTLP_ENDPOINT is set, so tests and fresh clones run without a
backend. The endpoint, headers (auth token, dataset) and protocol come from the standard OTEL_* variables.
"""

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .config import settings

log = logging.getLogger(__name__)


def exporting() -> bool:
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))


def setup_telemetry(service_name: str | None = None) -> None:
    """Install providers and exporters. Call once, before the app and the Elasticsearch client are created."""
    logging.basicConfig(level=logging.INFO)
    resource = Resource.create(
        {
            "service.name": service_name or settings.service_name,
            "deployment.environment.name": settings.deployment_environment,
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    meter_readers = []
    if exporting():
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        meter_readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=15_000))

        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
        set_logger_provider(logger_provider)
        logging.getLogger().addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))

    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=meter_readers))

    # The Elasticsearch 9 client traces itself through the global tracer provider set above, so every
    # Elasticsearch call becomes a child span of the request that made it; no extra instrumentor needed.
    log.info("telemetry ready (export %s)", "on" if exporting() else "off: OTEL_EXPORTER_OTLP_ENDPOINT not set")


def shutdown_telemetry() -> None:
    """Flush and stop exporters; short-lived commands call this so their spans are not lost."""
    for provider in (trace.get_tracer_provider(), metrics.get_meter_provider(), get_logger_provider()):
        if hasattr(provider, "shutdown"):
            provider.shutdown()


def instrument_app(app) -> None:
    # One server span per request; the per-message ASGI "send"/"receive" spans are noise for this app.
    FastAPIInstrumentor.instrument_app(app, exclude_spans=["send", "receive"])
